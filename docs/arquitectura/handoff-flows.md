# Flujos de Handoff entre Agentes — Sistema Multi-Agente

**Versión:** 3.1 (Tool-based Handoffs)
**Última actualización:** 2026-04-17
**Estado:** Implementado y verificado

---

## Flujo de Handoff Completo

```
                              ┌─────────────────────────────────────────────────────────┐
                              │                    SUPERVISOR                          │
                              │  (AgentSupervisor.process — enruta por intent/etapa)   │
                              └──────────────────────┬────────────────────────────────┘
                                                       │
                        ┌──────────────────────────────┼──────────────────────────────┐
                        │                              │                              │
                        ▼                              ▼                              ▼
               ┌────────────────┐             ┌──────────────────┐             ┌────────────────┐
               │ QualifierAgent │             │  PropertyAgent   │             │SchedulerAgent  │
               │ entrada        │             │ potencial        │             │calificacion_   │
               │ perfilamiento  │             │ (búsqueda)       │             │financiera      │
               └───────┬────────┘             └───────┬──────────┘             └───────┬────────┘
                       │                                │                                │
         ┌─────────────┼─────────────┐                │                                │
         │             │             │                │                                │
         ▼             ▼             ▼                ▼                                ▼
   ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌──────────────┐              ┌────────────────┐
   │ Scheduler │  │  Property  │  │ FollowUp  │  │ Qualifier    │              │  FollowUp      │
   │ Agent     │  │  Agent     │  │ Agent     │  │ Agent        │              │  Agent         │
   │ (DICOM    │  │ (sin       │  │ (DICOM     │  │ (cero         │              │ (post-         │
   │ clean)    │  │ resultados)│  │ dirty>    │  │ resultados)   │              │  appointment)  │
   └─────┬─────┘  └─────┬──────┘  └─────┬─────┘  └──────┬───────┘              └───────┬────────┘
         │              │               │               │                              │
         └──────────────┴───────────────┼───────────────┴──────────────────────────────┘
                                         │
                                         ▼
                               ┌──────────────────┐
                               │  FollowUpAgent   │
                               │ agendado         │
                               │ seguimiento      │
                               │ referidos        │
                               │ ganado           │
                               │ perdido          │
                               └────────┬─────────┘
                                        │
                                        │ (human request OR sentiment escalation)
                                        ▼
                               ┌──────────────────┐
                               │   HUMAN MODE     │
                               │ human_mode = True │
                               │ human_assigned_to │
                               └────────┬─────────┘
                                        │ (/conversations/leads/{id}/release)
                                        ▼
                               ┌──────────────────┐
                               │  AI RESUME       │
                               │ human_mode =     │
                               │ False            │
                               │ sentiment reset  │
                               └──────────────────┘
```

---

## Tabla de Handoffs por Agente

### QualifierAgent

| Handoff | Destino | Condición (código real) | Reason string | Mensaje de transición |
|---------|---------|------------------------|---------------|----------------------|
| → SchedulerAgent | `SchedulerAgent` | `all_required_fields_collected AND dicom_status in ("clean", "unknown")` | `"Lead calificado. Campos: [lista]. DICOM: clean."` | "Perfecto, te asigno una cita con un asesor." |
| → PropertyAgent | `PropertyAgent` | `lead.prefers_property_exploration BEFORE qualification_complete` | N/A (no handoff tool, cambio directo de estado) | "Te muestro las propiedades disponibles." |
| → FollowUpAgent | `FollowUpAgent` | `dicom_status == "has_debt" AND morosidad_amount > 500_000` | `"DICOM dirty — deuda alta"` | "Un asesor se comunicará contigo." |

**Handoffs entrantes:**

| Origen | Cuándo |
|--------|--------|
| PropertyAgent | Cuando `PropertyAgent._zero_results_handoff == True` (cero propiedades encontradas) |
| Supervisor | Por intent `financing_question` o etapa `entrada`/`perfilamiento` |

---

### PropertyAgent

| Handoff | Destino | Condición (código real) | Reason string | Mensaje de transición |
|---------|---------|------------------------|---------------|----------------------|
| → QualifierAgent | `QualifierAgent` | `_zero_results_handoff == True` (cero resultados para criterios) | N/A (capturado en context) | "No hay propiedades que coincidan. Necesito hacerte algunas preguntas." |
| → SchedulerAgent | `SchedulerAgent` | `lead wants to schedule_visit AFTER viewing properties` | N/A (capturado en context) | "Agendamos la visita." |

**Handoffs entrantes:**

| Origen | Cuándo |
|--------|--------|
| Supervisor | Por intent `property_search` (bypassea QualifierAgent) |
| QualifierAgent | Cuando lead quiere explorar propiedades antes de completar calificación |

---

### SchedulerAgent

| Handoff | Destino | Condición (código real) | Reason string | Mensaje de transición |
|---------|---------|------------------------|---------------|----------------------|
| → FollowUpAgent | `FollowUpAgent` | `appointment.confirmed == True` (después de `create_appointment`) | N/A (hand-off implícito post-creación) | "Tu visita está confirmada." |

**Handoffs entrantes:**

| Origen | Cuándo |
|--------|--------|
| QualifierAgent | DICOM clean + campos completos |
| PropertyAgent | Después de ver propiedades y querer agendar |
| Supervisor | Por intent `schedule_visit` o etapa `calificacion_financiera` |

---

### FollowUpAgent

| Handoff | Destino | Condición (código real) | Reason string | Mensaje de transición |
|---------|---------|------------------------|---------------|----------------------|
| → Human Mode | `human_mode=True` | `sentiment_escalation OR explicit_human_request` | `"Escalado a agente humano"` | "Te transfiero con un asesor." |
| → SchedulerAgent | `SchedulerAgent` | `lead wants reschedule` (desde etapa `seguimiento`) | N/A (capturado en context) | "Agendamos una nueva cita." |

**Handoffs entrantes:**

| Origen | Cuándo |
|--------|--------|
| QualifierAgent | DICOM dirty con morosidad > 500K |
| SchedulerAgent | Appointment confirmado |
| Supervisor | Etapa `agendado`, `seguimiento`, `referidos`, `ganado`, `perdido` |

---

## Human Mode

### Activación

```python
# Trigger en cualquier agente
lead.human_mode = True
lead.human_assigned_to = current_agent_id
lead.human_taken_at = datetime.utcnow()
```

**Condiciones de trigger:**
- `sentiment < -0.5` (escalación por sentimiento negativo)
- `explicit_human_request = True` (lead pide humano)

### Resume (AI)

```python
# Endpoint: POST /conversations/leads/{id}/release
lead.human_mode = False
lead.sentiment = empty_sentiment()  # reseteo
lead.human_release_note = optional_note
lead.human_mode_notified = False
```

---

## Routing del Supervisor

### Por Intent (primario)

| Intent | Agente asignado |
|--------|-----------------|
| `property_search` | PropertyAgent |
| `schedule_visit` | SchedulerAgent |
| `financing_question` | QualifierAgent |

### Por Etapa (fallback / sticky)

| Etapa | Agente |
|-------|--------|
| `entrada` | QualifierAgent |
| `perfilamiento` | QualifierAgent |
| `potencial` | PropertyAgent |
| `calificacion_financiera` | SchedulerAgent |
| `agendado` | FollowUpAgent |
| `seguimiento` | FollowUpAgent |
| `referidos` | FollowUpAgent |
| `ganado` | FollowUpAgent |
| `perdido` | FollowUpAgent |

### Sticky Agent

```python
if lead.current_agent and _AGENT_STILL_ACTIVE:
    return lead.current_agent  # no cambiar hasta que agent libere
```

---

## Herramientas de Handoff (Function Calling)

### QualifierAgent

```python
_HANDOVER_TOOLS = [
    LLMToolDefinition(
        name="handoff_to_scheduler",
        description="Transfiere al lead al agente deScheduler para agendar visitas",
        parameters={
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "qualification_data": {"type": "object"},
                "dicom_status": {"type": "string"},
            },
            "required": ["reason", "qualification_data", "dicom_status"],
        },
    ),
]
```

### PropertyAgent

```python
# Sin handoff tools propios — delega a QualifierAgent/SchedulerAgent vía contexto
```

### SchedulerAgent

```python
_HANDOVER_TOOLS = [
    LLMToolDefinition(
        name="get_available_appointment_slots",
        description="Obtiene horarios disponibles para agendar",
        parameters={"type": "object", "properties": {...}},
    ),
    LLMToolDefinition(
        name="create_appointment",
        description="Crea la cita en Google Calendar",
        parameters={"type": "object", "properties": {...}},
    ),
]
```

### FollowUpAgent

```python
_HANDOVER_TOOLS = [
    LLMToolDefinition(
        name="request_human",
        description="Escala a agente humano",
        parameters={
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
            },
            "required": ["reason"],
        },
    ),
]
```

---

## Edge Cases y Bugs Conocidos

### 1. DICOM dirty con morosidad ≤ 500K
- **Código:** `app/services/agents/qualifier.py`
- **Behavior:** El agente даёт orientación pero NO hace handoff — se queda en QualifierAgent
- **Bug:** No hay mensaje claro de por qué no se transfiere

### 2. PropertyAgent → QualifierAgent loop
- **Código:** `app/services/agents/property.py` con `_zero_results_handoff`
- **Protección:** `HANDOFF_LOOP_THRESHOLD = 3` en supervisor
- **Exception:** El handoff Property→Qualifier es permitido aunque haya loop detection

### 3. tool_mode_override ausente en SchedulerAgent
- **Código:** `app/services/agents/scheduler.py` líneas 203-211
- **Bug menor:** Falta `tool_mode_override="ANY"` explícito en llamada al LLM facade
- **Impacto:** Funcional (default es "ANY") pero inconsistente con otros agentes

### 4. Tipo de retorno incorrecto en GeminiProvider
- **Código:** `app/services/llm/providers/gemini_provider.py` línea 178
- **Bug:** Signature declara `-> Tuple[str, List[Dict]]` (2-tuple) pero retorna 3-tuple `(text, function_calls, usage)`
- **Workaround:** Facade maneja con `len(result) >= 3`

### 5. Variable redundante en scheduler.py
- **Código:** `app/services/agents/scheduler.py` línea 163
- **Bug:** `tools: list = list(_HANDOFF_TOOLS)` se sobrescribe en línea 178
- **Fix:** Eliminar línea 163

### 6. Handoff sin reason string
- **Código:** PropertyAgent → SchedulerAgent
- **Issue:** No genera reason string formal — depende del contexto implícito
- **Recomendación:** Estandarizar reason strings para todos los handoffs

---

## Resumen de Context Updates por Handoff

| Handoff | Context keys actualizadas |
|---------|--------------------------|
| QualifierAgent → SchedulerAgent | `qualification_data`, `dicom_status` |
| QualifierAgent → FollowUpAgent | `dicom_dirty_reason`, `morosidad_amount` |
| PropertyAgent → QualifierAgent | `_zero_results_handoff = True` |
| PropertyAgent → SchedulerAgent | `property_interest`, `selected_property_id` |
| SchedulerAgent → FollowUpAgent | `appointment_id`, `appointment_date`, `property_address` |
| FollowUpAgent → Human | `escalation_reason`, `sentiment_snapshot` |

---

## Changelog

| Fecha | Versión | Cambios |
|-------|---------|---------|
| 2026-04-17 | 3.1 | Migración a tool-based handoffs. Eliminación de keyword routing. `_STAGE_TO_AGENT` lookup en supervisor. |
| 2026-04-10 | 3.0 | Introducción de PropertyAgent. Routing por intent `property_search`. |
| 2026-03-28 | 2.5 | Human Mode con endpoint `/release`. Sentiment escalation trigger. |
| 2026-03-15 | 2.0 | Multi-agent system. QualifierAgent, SchedulerAgent, FollowUpAgent. |
| 2026-02-01 | 1.0 | Orchestrator monolítico inicial. |
