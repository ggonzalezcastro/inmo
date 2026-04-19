# Qualifier Agent

**Versión:** 1.0
**Última actualización:** 2026-04-17
**Carpeta:** `app/services/agents/qualifier/`

---

## 1. Propósito y Responsabilidad

El **QualifierAgent** es el primer agente especializado en el flujo de conversación con un lead. Su responsabilidad principal es:

- **Recopilar datos de contacto** del lead (nombre, teléfono, email, ubicación)
- **Realizar la calificación financiera preliminar** (ingresos, presupuesto, estado DICOM)
- **Aplicar la regla DICOM** para filtrar leads no calificables
- **Decidir cuándo hacer handoff** al siguiente agente (SchedulerAgent o PropertyAgent)

### Etapas del pipeline que gestiona

| Etapa | Descripción |
|-------|-------------|
| `entrada` | Primer contacto, saludos, validación de interés |
| `perfilamiento` | Recopilación de datos y calificación financiera |

---

## 2. Condiciones de `should_handle()`

El supervisor llama a `QualifierAgent.should_handle()` cuando se cumplen TODAS estas condiciones:

```python
lead.stage in (STAGE_ENTRADA, STAGE_PERFILAMIENTO)
AND agent_type == AGENT_TYPE_QUALIFIER  # Determinado por _STAGE_TO_AGENT
```

> **Nota:** La lógica de `should_handle()` es backward-compatible pero el supervisor no la llama directamente en el flujo normal. En su lugar, usa `_STAGE_TO_AGENT` para decisiones determinísticas de enrutamiento.

---

## 3. Flujo de `process()`

```
process(message: str, context: AgentContext, db: Session) -> AgentResponse
```

### Paso 1 — Reutilizar pre_analysis del orquestador

Si el orquestador ya realizó una llamada LLM (`context.pre_analysis`), se reutiliza para evitar llamadas duplicadas:

```python
if context.pre_analysis:
    analysis = context.pre_analysis
else:
    analysis = LLMServiceFacade.analyze_lead_qualification(
        message=message,
        lead_context=build_lead_context(context),
        broker_config=context.broker_config,
        agent_name=self.name,
    )
```

### Paso 2 — Mergear datos extraídos

Los campos extraídos por el LLM se fusionan con `lead_data` existente:

```python
merged_data = {**lead_data, **analysis.extracted_fields}
```

### Paso 3 — Aplicar regla DICOM (guardia a nivel de código)

```python
dirty_dicom = merged_data.get("dicom_status") in ("has_debt", "dirty")

if dirty_dicom:
    morosidad = merged_data.get("morosidad_amount", 0) or 0
    if morosidad > 500_000:
        # Handoff → FollowUpAgent con morosidad > 500k
        return emit_handoff_to_followup(
            merged_data,
            reason="morosidad_alta",
            guidance="Lead con morosidad > 500k no calificable para financier."
        )
    # Si morosidad <= 500k, se quedó en QualifierAgent (continuación normal)
```

### Paso 4 — Verificar si está completamente calificado

```python
if is_qualified(merged_data):
    # Emitir handoff → SchedulerAgent
    return emit_handoff(
        target_agent=AGENT_TYPE_SCHEDULER,
        handoff_context={...},
        reason="lead_calificado"
    )
```

### Paso 5 — Verificar interés en propiedades (ANTES de completar calificación)

```python
if has_property_interest(message):
    # Emitir handoff → PropertyAgent (lead pregunta por propiedades antes de estar calificado)
    return emit_handoff(
        target_agent=AGENT_TYPE_PROPERTY,
        handoff_context={...},
        reason="interes_propiedades"
    )
```

### Paso 6 — Retornar respuesta con context_updates

```python
return AgentResponse(
    text=analysis.response_text,
    context_updates={
        "lead_data": merged_data,
        "pending_fields": compute_pending_fields(merged_data),
    },
    agent=self.name,
)
```

---

## 4. Campos Recopilados

El QualifierAgent recopila los siguientes campos del lead:

### Datos de contacto

| Campo | Descripción | Tipo |
|-------|-------------|------|
| `name` | Nombre completo del lead | string |
| `phone` | Teléfono de contacto | string |
| `email` | Correo electrónico | string |
| `location` | Comuna / sector de interés | string |

### Datos financieros

| Campo | Descripción | Tipo |
|-------|-------------|------|
| `salary` / `monthly_income` | Renta mensual informada | float |
| `budget` | Presupuesto disponible para la propiedad | float |
| `dicom_status` | Estado crediticio: `clean`, `dirty`, `has_debt`, `unknown` | enum |
| `morosidad_amount` | Monto de morosidad si DICOM está sucio | float |

---

## 5. Puerta de Pre-calificación

```python
def is_qualified(self, lead_data: dict) -> bool:
    """Datos mínimos para calificación financiera"""
    has_name = bool(lead_data.get("name"))
    has_phone = bool(lead_data.get("phone"))
    has_financial = bool(
        lead_data.get("budget") or lead_data.get("salary") or lead_data.get("monthly_income")
    )
    dicom = lead_data.get("dicom_status", "unknown")
    dicom_ok = dicom in ("clean", "unknown")

    return has_name and has_phone and has_financial and dicom_ok
```

> Un lead está "calificado" cuando tiene: nombre + teléfono + (presupuesto O renta) + DICOM limpio o desconocido.

---

## 6. Estrategia de Campos Pendientes

Para no abrumar al lead, el agente solicita **máximo 3 campos por mensaje**. Los campos restantes se agrupan por estrategia:

```python
PENDING_FIELD_GROUPS = {
    "contact": ["phone", "email"],           # Nunca más de 2
    "location": ["location", "commune"],     # Máximo 2
    "financial": ["salary", "budget"],       # Máximo 2
    "dicom": ["dicom_status"],               # Siempre 1
}
```

---

## 7. Construcción del System Prompt

El `get_system_prompt()` ensambla el prompt del sistema en el siguiente orden:

```python
def get_system_prompt(self, context: AgentContext) -> str:
    parts = []

    # 1. Plantilla del broker o default QUALIFIER_SYSTEM_PROMPT
    parts.append(self._get_base_template(context))

    # 2. Inyectar campos ya recopilados
    parts.append(self._inject_collected_fields(context.lead_data))

    # 3. Inyectar campos pendientes (máx 3 por mensaje)
    parts.append(self._inject_pending_fields(context.lead_data, max_fields=3))

    # 4. Añadir instrucción de herramientas de handoff
    parts.append(HANDOFF_TOOLS_INSTRUCTION)

    # 5. Añadir instrucción de saludo (según estado de conversación)
    parts.append(self._get_greeting_instruction(context.conversation_state))

    # 6. Recordatorio de prohibición DICOM (NO mencionar montos de financiamiento)
    parts.append(DICOM_PROHIBITION_REMINDER)

    # 7. Inyectar skill si no hay prompt custom
    if not context.broker_config.has_custom_prompt:
        parts.append(QUALIFIER_SKILL)

    # 8. Inyectar contexto de handoff si viene del PropertyAgent
    if context.handoff_from == AGENT_TYPE_PROPERTY:
        parts.append(PROPERTY_HANDOFF_CONTEXT)

    # 9. Inyectar tone_hint si lead está frustrado
    if context.is_frustrated:
        parts.append(TONE_HINT_FRUSTRATED)

    # 10. Inyectar human_release_note si existe
    if context.human_release_note:
        parts.append(f"Nota de liberación: {context.human_release_note}")

    return "\n\n".join(filter(None, parts))
```

### Resumen de componentes del prompt

| # | Componente | Fuente |
|---|------------|--------|
| 1 | Base template | `BrokerPromptConfig` o default |
| 2 | Campos recopilados | `lead_data` |
| 3 | Campos pendientes | `lead_data` (máx 3) |
| 4 | Herramientas de handoff | `_HANDOFF_TOOLS` |
| 5 | Instrucción de saludo | `conversation_state` |
| 6 | Prohibición DICOM | Constante hardcodeada |
| 7 | Skill (si aplica) | `QUALIFIER_SKILL` |
| 8 | Contexto de handoff | `handoff_from` |
| 9 | Hint de tono | `is_frustrated` |
| 10 | Nota de liberación | `human_release_note` |

---

## 8. Herramientas de Handoff (Outgoing)

El QualifierAgent define `_HANDOFF_TOOLS` para comunicar al LLM cuándo debe transferir la conversación:

```python
_HANDOFF_TOOLS = [
    make_handoff_tool(
        "scheduler",
        description="Llama cuando lead está completamente calificado (nombre, teléfono, email, ubicación, renta) y DICOM limpio."
    ),
    make_handoff_tool(
        "property",
        description="Llama cuando lead pregunta por propiedades ANTES de completar calificación."
    ),
]
```

### Cuándo se usa cada handoff

| Handoff a | Condición | Ejemplo |
|-----------|-----------|---------|
| `scheduler` | Lead completo + DICOM limpio | `"Tengo Juan, 9M presupuesto, DICOM limpio"` |
| `property` | Lead pregunta por propiedades antes de estar calificado | `"¿Qué departamentos tienen?"` antes de dar datos |

---

## 9. Handoff Entrante (desde PropertyAgent)

Cuando el lead viene derivado del `PropertyAgent`, el QualifierAgent recibe:

```python
context.handoff_from = AGENT_TYPE_PROPERTY
context.handoff_context = {
    "property_interest": str,      # Tipo de propiedad buscada
    "budget_hint": Optional[float], # Presupuesto mencionado
    "location_hint": Optional[str],  # Sector de interés
}
```

El prompt injerta esta información para no pedir datos ya recopilados:

```
[CONTEXTO DEL PROPERTY AGENT]
El lead ya expresó interés en: {property_interest}
Presupuesto mentioned: {budget_hint}
Sector de interés: {location_hint}
→ No solicitar estos datos nuevamente, continuar con campos faltantes.
```

---

## 10. Regla DICOM Explicada

### Lógica de negocio

| DICOM status | Monto morosidad | Acción |
|--------------|-----------------|--------|
| `clean` | — | Calificación normal, continuar |
| `unknown` | — | Calificación normal, solicitar DICOM |
| `dirty` / `has_debt` | ≤ 500.000 | Continuar en QualifierAgent, dar orientación |
| `dirty` / `has_debt` | > 500.000 | Handoff a FollowUpAgent (no calificable) |

### Prohibición absoluta

Cuando el lead pregunta sobre **financiamiento, crédito, pie, cuotas, tasas**:

> **Respuesta permitida:**
> ```
> "Eso lo revisamos en detalle con nuestro ejecutivo en la reunión.
>  ¿Te agendamos una videollamada para orientarte?"
> ```

> **NUNCA responder con:**
> - Porcentajes de pie (20%, 30%)
> - Rangos de crédito
> - Estimaciones de cuotas
> - La palabra "pre-aprobación"

### Implementación de la guardia

```python
dirty_dicom = merged_data.get("dicom_status") in ("has_debt", "dirty")
if dirty_dicom:
    morosidad = merged_data.get("morosidad_amount", 0) or 0
    if morosidad > 500_000:
        # Código hardcodeado: hacer handoff a FollowUpAgent
        # NO depende del LLM para esta decisión
```

> **Importante:** La regla DICOM es una **guardia a nivel de código**, no una decisión del LLM. Esto garantiza que incluso si el LLM no followea las instrucciones, el sistema enforced correctamente la política.

---

## 11. Lógica de Saludo

El primer mensaje del agente varía según el contexto:

### Primera vez (sin nombre en lead_data)

```
¡Hola! Soy {agent_name} de {broker_name} 😊
¿Con quién tengo el gusto?
```

### Primera vez (con nombre del lead)

```
¡Hola {name}! Soy {agent_name} de {broker_name}.
¿En qué te puedo ayudar?
```

### Conversación activa

- **NO se repite el saludo**
- Se continúa directamente con el campo pendiente siguiente

### Handoff desde otro agente

- **NO se repite introducción**
- Continuación natural: `"Perfecto {name}, tenía algunas preguntas para conocerte mejor..."`

---

## 12. Estados de Conversación

El QualifierAgent utiliza `conversation_state` para decidir cómo responder:

| Estado | Descripción | Comportamiento |
|--------|-------------|----------------|
| `GREETING` | Primera vez sin contexto | Mostrar saludo + solicitud de nombre |
| `INTEREST_CHECK` | Verificando nivel de interés | Preguntar directamente por intención de compra/arriendo |
| `DATA_COLLECTION` | Recopilando datos | Solicitar campos pendientes (máx 3) |
| `FINANCIAL_QUAL` | Calificación financiera | Preguntar por ingresos, presupuesto, DICOM |

### Transiciones

```
GREETING → INTEREST_CHECK (al recibir nombre)
INTEREST_CHECK → DATA_COLLECTION (al confirmar interés)
DATA_COLLECTION → FINANCIAL_QUAL (al tener datos básicos)
FINANCIAL_QUAL → (handoff) → SchedulerAgent
```

---

## 13. Métricas de Evaluación

El QualifierAgent es evaluado con las siguientes métricas determinísticas (regex-based, sin LLM judge):

| Métrica | Descripción | Pass criteria |
|---------|-------------|---------------|
| `DicomRuleMetric` | No menciona montos de financiamiento cuando DICOM dirty | Regex: no matches para patrones de crédito |
| `FieldCollectionMetric` | Todos los campos requeridos recopilados | Todos los campos en `is_qualified()` presentes |
| `HandoffTimingMetric` | Handoff a scheduler solo cuando fully qualified | Sin handoff premature |
| `HandoffPropertyMetric` | Handoff a property cuando lead pregunta antes de calificación | Handoff correcto en conversación |

---

## 14. Configuración del Agente

```python
class QualifierAgent(BaseAgent):
    name = "Sofía"
    agent_type = AGENT_TYPE_QUALIFIER
    owned_stages = [STAGE_ENTRADA, STAGE_PERFILAMIENTO]
    owned_states = [GREETING, INTEREST_CHECK, DATA_COLLECTION, FINANCIAL_QUAL]

    # Umbrales
    MOROSIDAD_THRESHOLD = 500_000

    # Estrategia de campos
    MAX_PENDING_FIELDS_PER_MESSAGE = 3

    # Tool mode override (let LLM decide when to handoff)
    tool_mode_override = "AUTO"
```

---

## 15. Ejemplo de Conversación

```
Lead:    Hola, quiero ver departamentos en Providencia
Agent:   ¡Hola! Soy Sofía de Inmo 😊 ¿Con quién tengo el gusto?
Lead:    Soy Carlos, 56 años
Agent:   ¡Hola Carlos! Cuéntame, ¿estás buscando comprar o arrendar?
Lead:    Comprar, tengo un presupuesto de 45 millones
Agent:   Perfecto. Para ayudarte mejor, ¿me podrías dar tu correo y teléfono?
Lead:    carlos@mail.com + 56912345678
Agent:   Gracias. ¿Sabes cuál es tu situación en DICOM actualmente?
Lead:    Creo que estoy limpio
Agent:   ¿Podrías indicarme tus ingresos mensuales aprox?
Lead:    2.5 millones
Agent:   Perfecto Carlos, tienes todo listo. Voy a transferirte a nuestro equipo...
(Handoff → SchedulerAgent)
```

---

## Changelog

| Fecha | Versión | Cambios |
|-------|---------|---------|
| 2026-04-17 | 1.0 | Versión inicial del documento. Incluye propósito, flujo process(), campos recopilados, construcción de prompt, handoffs, regla DICOM, lógica de saludo y estados de conversación. |