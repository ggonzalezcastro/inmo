# PropertyAgent

**Versión:** 1.0
**Fecha:** 2026-04-18
**Proyecto:** AI Lead Agent Pro — Inmo CRM
**Agente:** PropertyAgent (Agente de búsqueda de propiedades)

---

## 1. Descripción General

El **PropertyAgent** es el agente especializado en **búsqueda e itineración de propiedades**. Actúa cuando el lead se encuentra en stage `potencial` o cuando el QualifierAgent le entrega un lead interesado en buscar propiedades.

Su responsabilidad es traducir las preferencias del lead (mencionadas en lenguaje natural) en parámetros de búsqueda estructurados, ejecutar una búsqueda híbrida (SQL + vectorial), presentar resultados y facilitar el interés del lead para agendar una visita.

**No touch**: scoring financiero, DICOM, pie, cuotas — eso es del QualifierAgent.

---

## 2. Activación

### Stage routing

| Stage | ¿Activo? | Notas |
|---|---|---|
| `entrada` | Parcial | Solo si hay intención de búsqueda detectada |
| `perfilamiento` | Parcial | Solo si hay intención de búsqueda detectada |
| `potencial` | **Sí** | Stage primario del PropertyAgent |
| `calificacion_financiera` | No | Cede al QualifierAgent |
| `agendado` | No | Cede al SchedulerAgent |

### Handoff de entrada

El QualifierAgent puede transferir leads al PropertyAgent cuando detectan interés activo en buscar propiedades (`property_search_intent`). El PropertyAgent también recibe handoffs del SchedulerAgent si el lead quiere buscar más opciones antes de agendar.

---

## 3. Herramientas

### 3.1 `search_properties` — Búsqueda híbrida

```python
SEARCH_PROPERTIES_TOOL = {
    "name": "search_properties",
    "description": "Busca propiedades disponibles por parámetros estructurados...",
    "parameters": {
        "type": "object",
        "properties": {
            "commune":         {"type": "string"},
            "property_type":   {"type": "string"},
            "bedrooms_min":    {"type": "integer"},
            "bathrooms_min":   {"type": "integer"},
            "price_max_uf":    {"type": "number"},
            "price_min_uf":    {"type": "number"},
            "area_min":        {"type": "number"},
            "amenities":       {"type": "array", "items": {"type": "string"}},
            "strategy":        {"type": "string", "enum": ["sql", "semantic", "hybrid"]},
            "limit":           {"type": "integer"},
        },
        "required": []
    }
}
```

**Estrategias:**

| Estrategia | Cuándo usarla |
|---|---|
| `hybrid` (default) | Parámetros estructurados — combina SQL filters + vector similarity con RRF merge |
| `semantic` | Solo palabras cualitativas ("luminoso", "tranquilo", "con vista") — busca por embedding |
| `sql` | Parámetros exactos que mappean directo a columnas — filtrado puro |

**Resultado:**

```json
{
  "count": 3,
  "properties": [
    {
      "id": 42,
      "name": "Depto en Las Condes",
      "property_type": "departamento",
      "commune": "Las Condes",
      "price_uf": 4500,
      "bedrooms": 3,
      "bathrooms": 2,
      "square_meters_total": 85,
      "highlights": "Vista panorámica, luminoso",
      "amenities": ["gimnasio", "piscina"],
      "images": [{"url": "...", "caption": "Living"}]
    }
  ]
}
```

### 3.2 Handoff tools

```python
_HANDOFF_TOOLS = [
    make_handoff_tool(
        "qualifier",
        "Llama cuando el usuario pregunte sobre financiamiento, DICOM, renta o crédito. "
        "El agente calificador maneja esas consultas."
    ),
    make_handoff_tool(
        "scheduler",
        "Llama cuando el usuario quiere visitar o agendar cita para una propiedad concreta."
    ),
]
```

| Herramienta | Cuándo llamarla |
|---|---|
| `handoff_to_qualifier` | Pregunta financiera, DICOM, pie, cuotas, crédito, renting, leasing |
| `handoff_to_scheduler` | Quiere agendar/visitar una propiedad específica |
| `search_properties` | Búsqueda/refinamiento de propiedades |

---

## 4. Flujo de procesamiento

```
process(message, context, db)
  │
  ├─ get_system_prompt()
  │    └─ Construye prompt con:
  │         • Nombre del agente (de broker config)
  │         • Budget context (de lead_data)
  │         • Property preferences (de lead_metadata)
  │         • DICOM status (del lead)
  │         • Instrucciones especiales si lead no calificado
  │         • PROHIBIDO: nunca mencionar pie %, rangos financieros
  │
  ├─ _build_messages(history, message)
  │    └─ Convierte message_history + nuevo mensaje → LLMMessage[]
  │
  ├─ LLMServiceFacade.generate_response_with_function_calling()
  │    ├─ tools = [SEARCH_PROPERTIES_TOOL] + _HANDOFF_TOOLS
  │    └─ tool_executor callback
  │
  ├─ tool_executor():
  │    ├─ search_properties → execute_property_search() → PropertyService
  │    ├─ handoff_to_qualifier → captura intent, limpia texto LLM si 0 resultados
  │    └─ handoff_to_scheduler → captura intent
  │
  └─ AgentResponse(message, handoff?, function_calls)
       └─ Si zero_results=True:
            • Transición determinista (no LLM raw text)
            • Handoff a QualifierAgent
            • context_updates con _zero_results_handoff
```

---

## 5. System Prompt

El prompt se arma dinámicamente con estos bloques:

```
{hader con agent_name y broker_name}

## Contexto del cliente
{budget_ctx}
Zona de interés: {location}
Estado DICOM: {dicom_status}

## Preferencias de propiedad registradas
{prefs_ctx}

## Tu rol
- Busca propiedades disponibles usando la herramienta `search_properties`
- Presenta los resultados de forma clara, destacando lo más relevante
- NO ofrezcas agendar visitas — eso lo maneja otro agente
- NO preguntes sobre presupuesto, renta, DICOM — eso lo maneja otro agente

## Cómo usar la herramienta de búsqueda
1. Extrae parámetros del mensaje del cliente
2. Usa strategy="hybrid" por defecto
3. Si menciona solo características cualitativas → strategy="semantic"
4. Devuelve máximo 3-5 propiedades

## Formato de presentación
Por cada propiedad:
- Nombre/tipo y ubicación
- Precio en UF
- Dormitorios, baños, m²
- Highlights más relevantes
- Amenidades clave

## HERRAMIENTAS DE TRASPASO
- Financiera/DICOM → handoff_to_qualifier INMEDIATAMENTE
- Quiere agendar → handoff_to_scheduler
- Rechazo / "no" → handoff_to_qualifier

## PROHIBIDO ABSOLUTO
NUNCA menciones porcentajes de pie, rangos ('10% a 20%'), montos, cuotas.
Ante cualquier pregunta financiera → handoff_to_qualifier de inmediato.
```

**Special block para leads no calificados** (stages `entrada`/`perfilamiento` sin datos):

```
[INSTRUCCIÓN ESPECIAL]
1. PRIMERO muestra las propiedades encontradas tal como son
2. Si hay resultados: al final haz UNA pregunta natural para refinar
3. NUNCA digas 'no encontramos', 'no hay', 'lamentablemente'
4. NUNCA pidas los datos ANTES de responder sobre las propiedades
5. Si el usuario dice 'no', 'no importa' → handoff_to_qualifier de inmediato
```

---

## 6. Decisiones de diseño

### 6.1 Zero-results → handoff determinista

Cuando `search_properties` devuelve 0 resultados, el agente **no permite** que el LLM genere texto libre como "no hay propiedades disponibles". En cambio:

1. Captura `_handoff_intent["zero_results"] = True`
2. Construye transición determinista basada en si el lead ya tiene nombre + teléfono
3. Emite `HandoffSignal(target=QualifierAgent)` con reason `"Lead listo para proceso de calificación"`

**Razón**: La regla de negocio dice que nunca se debe revelar disponibilidad al lead. El LLM podría filtrar "no hay opciones" en texto inline, violando esta regla.

### 6.2 hybrid search con RRF

El `execute_property_search()` del `PropertyService` combina:

- **SQL filters**: commune, bedrooms, price range (postgresql WHERE clause)
- **Vector similarity**: description + highlights + amenities embedding (cosine distance)
- **RRF merge**: `1/(rank_sql + rank_vector + k)` — fusiona rankings sin un权重 fijo

### 6.3 Contexto de compresión

El `LeadContextService.get_lead_context()` aplica compresión de contexto antes de llegar al agente. El PropertyAgent recibe `message_history` ya comprimido por el `ContextManager`.

---

## 7. Estados de error

| Error | Comportamiento |
|---|---|
| `search_properties` falla | Loguea error, retorna `{"error": "...", "properties": []}`, permite al LLM responder con mensaje de fallback |
| LLM call falla | Catch exception, retorna mensaje de disculpa + re-pregunta qué busca |
| Zero results | Handoff determinista a QualifierAgent (no texto libre del LLM) |
| Handoff LLM raw text vacío | Usa transición predefinida ("Claro, déjame conectarte...") |

---

## 8. Métricas de observabilidad

```python
event_logger.log_property_search(
    lead_id=..., broker_id=..., search_params=..., strategy=...,
    results_count=..., top_result_ids=...
)
event_logger.log_tool_call(
    tool_name="search_properties", tool_input=..., tool_output=...,
    latency_ms=..., success=..., agent_type="property"
)
```

---

## 9. Relaciones con otros agentes

```
                    ┌─────────────────────┐
                    │   Entry Point        │
                    │ (telegram/whatsapp/  │
                    │  webchat message)   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  AgentSupervisor     │
                    │  _select_agent()    │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │ Qualifier   │────▶│  Property   │────▶│  Scheduler  │
   │  Agent     │     │   Agent     │     │   Agent     │
   │            │◀────│             │     │             │
   │ DICOM,     │ handoff  Búsqueda │ handoff  Agendar  │
   │ perfil     │     │  propiedades│     │   visita    │
   └─────────────┘     └─────────────┘     └─────────────┘
          ▲                    │                    │
          │         zero_results                    │
          │         o interés financiero           │
          └────────────────────────────────────┘
                         Handoff
```

| Del Agent | Al Agent | Trigger |
|---|---|---|
| QualifierAgent | PropertyAgent | `property_search_intent` en lead_metadata |
| PropertyAgent | QualifierAgent | Pregunta financiera o zero_results |
| PropertyAgent | SchedulerAgent | Lead quiere agendar visita |
| SchedulerAgent | PropertyAgent | Lead quiere buscar más opciones |

---

## 10. Changelog

| Fecha | Versión | Cambios |
|---|---|---|
| 2026-04-18 | 1.0 | Creación del documento. Agente confirmado existente en `backend/app/services/agents/property.py` (440 líneas). |
