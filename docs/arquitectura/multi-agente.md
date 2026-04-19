# Arquitectura Multi-Agente — Sistema de qualification y agendado

**Fecha:** 17 de abril de 2026  
**Versión:** 3.1 (Tool-based Handoffs)

---

## 1. Vision General

El sistema multi-agente es un orquestador de agentes IA especializados que gestionan el ciclo de vida de un lead inmobiliario chileno desde su captura hasta el cierre (ganado/perdido). Cada agente es responsable de una fase distinta del pipeline y delega al siguiente agente mediante un mecanismo de **handoff basado en herramientas**.

```
┌─────────────────────────────────────────────────────────────────┐
│                     AgentSupervisor                             │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  process(message, AgentContext, db)                      │  │
│  │  Loop max 3 hops:                                        │  │
│  │    1. _select_agent() ──► determina quién atiende         │  │
│  │    2. agent.process() ──► ejecuta lógica del agente       │  │
│  │    3. acumulan context_updates / message_history          │  │
│  │    4. should_handoff()? ──► si sí, siguiente hop         │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │ Qualifier   │───▶│ Property    │───▶│ Scheduler   │
   │   Agent     │    │   Agent     │    │   Agent     │
   └─────────────┘    └─────────────┘    └─────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                     ┌─────────────┐
                     │ Follow_Up    │
                     │   Agent      │
                     └─────────────┘
```

---

## 2. Tipos de Agente — AgentType Enum

```python
class AgentType(str, Enum):
    QUALIFIER = "qualifier"    # Recopila datos del lead + qualification financiera
    SCHEDULER  = "scheduler"    # Agenda visitas a propiedades
    FOLLOW_UP  = "follow_up"    # Engagement post-visita / referrals
    PROPERTY   = "property"     # Busqueda híbrida + recomendaciones de propiedades
    SUPERVISOR = "supervisor"   # Interno: enruta entre agentes
```

| Agente       | Responsabilidad principal                              | Etapas que atiende                               |
|--------------|--------------------------------------------------------|--------------------------------------------------|
| Qualifier    | Captura datos personales, salary, budget, DICOM status | entrada, perfilamiento                           |
| Property     | Busqueda y recomendacion de propiedades               | potencial                                        |
| Scheduler    | Agenda visitas (llamada vocal via VAPI)                | calificacion_financiera                         |
| Follow_Up    | Post-visita, cierre, referidos                        | agendado, seguimiento, referidos, ganado, perdido|
| Supervisor   | Solo interno — selecciona y enruta                     | (ninguna — no procesa mensajes directamente)     |

---

## 3. seleccion de Agente — _select_agent()

### 3.1 Algoritmo completo

```
_in_select_agent(message, context):
│
├─ 1. STICKY AGENT
│   └─ Si context.current_agent esta configurado
│       └─ Mantener ese agente (no re-seleccionar)
│
├─ 2. INTENT-BASED ROUTING  (pre_analysis del orchestrator)
│   ├─ intent == "property_search"  ──▶ PropertyAgent
│   ├─ intent == "schedule_visit"   ──▶ SchedulerAgent
│   └─ intent == "financing_question" ──▶ QualifierAgent
│       (tiene prioridad sobre etapa — aun en etapa "agendado")
│
├─ 3. STAGE-BASED ROUTING  (tabla _STAGE_TO_AGENT)
│   │
│   │  "entrada"                ──▶ QualifierAgent
│   │  "perfilamiento"          ──▶ QualifierAgent
│   │  "potencial"              ──▶ PropertyAgent
│   │  "calificacion_financiera"───▶ SchedulerAgent
│   │  "agendado"               ──▶ FollowUpAgent
│   │  "seguimiento"            ──▶ FollowUpAgent
│   │  "referidos"              ──▶ FollowUpAgent
│   │  "ganado"                 ──▶ FollowUpAgent
│   │  "perdido"                ──▶ FollowUpAgent
│   │
│
└─ 4. FALLBACK
    └─ Etapa desconocida ──▶ QualifierAgent
```

### 3.2 Mapeo completo — _STAGE_TO_AGENT

```python
_STAGE_TO_AGENT: Dict[str, AgentType] = {
    "entrada":                   AgentType.QUALIFIER,
    "perfilamiento":             AgentType.QUALIFIER,
    "potencial":                 AgentType.PROPERTY,
    "calificacion_financiera":   AgentType.SCHEDULER,
    "agendado":                  AgentType.FOLLOW_UP,
    "seguimiento":               AgentType.FOLLOW_UP,
    "referidos":                 AgentType.FOLLOW_UP,
    "ganado":                    AgentType.FOLLOW_UP,
    "perdido":                   AgentType.FOLLOW_UP,
}
```

---

## 4. AgentContext — Estado compartido

```python
@dataclass
class AgentContext:
    lead_id: int
    broker_id: int
    pipeline_stage: str                    # e.g. "entrada", "perfilamiento", "agendado"
    conversation_state: str                # e.g. "DATA_COLLECTION"
    lead_data: Dict[str, Any]              # name, phone, email, salary, budget, location, dicom_status
    message_history: List[Dict]            # [{role, content}, ...]
    current_agent: Optional[AgentType] = None
    handoff_count: int = 0                 # guarda contra loops infinitos
    pre_analysis: Optional[Dict[str, Any]] = None  # del orchestrator paso 3b
    current_message: Optional[str] = None
    property_preferences: Dict[str, Any] = field(default_factory=dict)
    human_release_note: Optional[str] = None
    last_agent_note: Optional[str] = None
    current_frustration: float = 0.0
    tone_hint: Optional[str] = None         # "empathetic", "professional", "concise"
```

---

## 5. Mecanismo de Handoff

### 5.1 Principio general

Cada agente tiene `_HANDOFF_TOOLS` — definiciones de herramientas que se pasan al LLM. Cuando el LLM determina que el lead esta listo para pasar al siguiente agente, invoca la herramienta de handoff. El tool executor captura el intento en un `HandoffSignal`.

```python
@dataclass
class HandoffSignal:
    target_agent: AgentType
    reason: str
    context_updates: Dict[str, Any] = field(default_factory=dict)
```

### 5.2 Factoria de herramientas de handoff

```python
def make_handoff_tool(target_agent: str, description: str) -> LLMToolDefinition:
    return LLMToolDefinition(
        name=f"handoff_to_{target_agent}",
        description=description,
        parameters={
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Motivo del traspaso"}
            },
            "required": ["reason"],
        },
    )
```

### 5.3 Handoff tools por agente

**QualifierAgent:**
- `handoff_to_scheduler` —trigger: lead completamente calificado (name, phone, email, location, salary) y DICOM limpio
- `handoff_to_property` — trigger: lead quiere explorar propiedades ANTES de completar la qualification

**PropertyAgent:**
- `handoff_to_qualifier` — trigger: se detecta necesidad de mas datos del lead
- `handoff_to_scheduler` — trigger: lead desea agendar visita

**SchedulerAgent:**
- `handoff_to_follow_up` — trigger: cita confirmada exitosamente

**FollowUpAgent:**
- `handoff_to_property` — trigger: lead quiere ver mas propiedades (re-ingreso al funnel)
- Sin handoff a otros agentes en etapa ganado/perdido (terminal)

### 5.4 Control del LLM — tool_mode_override

| Valor      | Comportamiento                                                |
|------------|---------------------------------------------------------------|
| `"ANY"`    | Fuerza function calling — LLM DEBE usar una tool si esta disponible |
| `"AUTO"`   | LLM decide si usa tool o responde con texto libre            |

La mayoria de los agentes usan `"AUTO"` por defecto. QualifierAgent y SchedulerAgent usan `"ANY"` para garantizar que el handoff ocurra cuando corresponde.

---

## 6. Supervisor.process() — Flujo completo

```
process(message, context, db):
│
├─ 1. Inject mensaje actual en context.current_message
│
├─ 2. Warm-up cache Redis con configs de modelo del agente
│
├─ 3. Loop (max _MAX_HANDOFFS = 3 hops):
│   │
│   ├─ a. _select_agent() ──► obtiene agente para este hop
│   │
│   ├─ b. Loop detection:
│   │       si mismo agente aparecio dos veces consecutivamente
│   │       y no hay excepcion de zero-results ──▶ romper loop
│   │
│   ├─ c. agent.process(message, context, db)
│   │       └─ retorna AgentResponse
│   │
│   ├─ d. Acumular context_updates de todos los hops (H5)
│   │
│   ├─ e. Aplicar context_updates al contexto
│   │
│   ├─ f. Verificar handoff: agent.should_handoff()
│   │
│   ├─ g. Si hay handoff:
│   │       ├─ Actualizar message_history con respuesta del agente
│   │       ├─ Incrementar handoff_count
│   │       └─ Continuar siguiente iteracion del loop
│   │
│   └─ h. Si no hay handoff:
│           └─ Romper loop, retornar respuesta
│
├─ 4. Marcar handoff context como consumido:
│      _last_consumed_handoff_at = now()
│
└─ 5. Retornar ultima respuesta con metadata acumulada
```

### 5.1 AgentResponse

```python
@dataclass
class AgentResponse:
    message: str
    agent_type: AgentType
    context_updates: Dict[str, Any] = field(default_factory=dict)
    handoff: Optional[HandoffSignal] = None
    function_calls: List[Dict] = field(default_factory=list)
    tokens_used: int = 0
    is_final: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
```

---

## 7. Proteccion contra loops — Max Hops

```python
_MAX_HANDOFFS = 3
```

El supervisor limita a 3 saltos entre agentes por cada mensaje del lead. Esto previene:

1. **Loops infinitos** entre agentes que no logran consenso sobre quien debe atender
2. **Agentes repetitivos** que se devuelven sin resolver nada
3. **Excepciones silenciosas** que causan reintentos automaticos indefinidos

### Logica de deteccion de loop

```
Si (agente_actual == agente_anterior) AND (no hubo zero-results exception):
    └─ Romper loop — mismo agente dos veces = loop
```

Excepcion: `PropertyAgent → QualifierAgent` esta permitida porque puede haber besoin de mas datos antes de buscar propiedades.

---

## 8. Persistencia de contexto entre Handoffs

### 8.1 message_history

El historial de mensajes se preserva integro a traves de todos los hops (H3). Cada agente puede leer la conversacion completa.

### 8.2 context_updates

Los updates de contexto se **acumulan** a traves de todos los hops (H5). Se incluyen:

```python
{
    "_handoff_reason": "lead fully qualified, DICOM clean",
    "_handoff_from": "qualifier",
    "_handoff_at": "2026-04-17T10:30:00Z",
    "current_agent": AgentType.SCHEDULER,
    # ... cualquier otro campo modificado por el agente
}
```

### 8.3 current_agent persistente

`current_agent` se persiste en `lead_metadata` del lead. Esto permite que si la conversacion se corta y se retoma, el supervisor pueda reanudar con el ultimo agente activo (sticky agent).

---

## 9. Manejo de errores

| Codigo | Descripcion                                                               |
|--------|---------------------------------------------------------------------------|
| G2     | Excepciones en `agent.process()` son capturadas y retornan respuesta de error graceful |
| Loop detection | Deteccion de agentes repetidos (seccion 7)                          |
| Circuit breaker | Corte de llamadas LLM despues de max_retries agotados              |

---

## Changelog

| Fecha       | Version | Cambio                                                   |
|-------------|---------|----------------------------------------------------------|
| 2026-04-17  | 3.1     | Handoffs basados en herramientas (tool-based) — se eliminaron keyword regex |
| 2026-04-17  | 3.0     | Routing por intent desde pre_analysis del orchestrator     |
| 2026-04-17  | 2.0     | AgentSupervisor con sticky agent y stage lookup table      |
| 2026-04-17  | 1.0     | Orquestador unico con BaseAgent.should_handle() abstracto  |
