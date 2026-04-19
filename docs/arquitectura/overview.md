# Arquitectura del Sistema Inmo — Agente IA para Corretaje Inmobiliario

> **Última actualización:** 2026-04-17

## Tabla de Contenidos

1. [[#introduccion|Introducción]]
2. [[#stack-tecnologico|Stack Tecnológico]]
3. [[#arquitectura-general|Arquitectura General]]
4. [[#flujo-de-datos|Flujo de Datos]]
5. [[#estructura-del-proyecto|Estructura del Proyecto]]
6. [[#modelos-de-datos|Modelos de Datos]]
7. [[#servicios-clave|Servicios Clave]]
8. [[#agentes-multi-ia|Agentes Multi-IA]]
9. [[#integraciones-externas|Integraciones Externas]]
10. [[#multi-tenancy|Multi-Tenancy]]
11. [[#changelog|Changelog]]

---

## 1. Introducción {#introduccion}

Inmo es un CRM inmobiliario multi-tenant potenciado por un agente IA llamado **Sofía**. El agente interactúa con prospectos a través de WhatsApp, Telegram y webchat, los califica, responde preguntas sobre propiedades y agenda visitas. Todo opera sobre una arquitectura de microservicios con fallback entre proveedores de LLM y ejecución asíncrona de tareas pesadas.

**Principios rectores:**

- **Multi-tenancy estricto:** cada Broker (corredora) tiene acceso únicamente a sus propios leads, agentes y configuración IA.
- **LLM Router con failover:** Gemini como proveedor primario; si falla, pasa a Claude; si falla again, a OpenAI.
- **Agentes especializados con handovers basados en herramientas:** en lugar de regex frágil, el LLM decide cuándo transferir un lead de un agente a otro.
- **PII encriptado:** campos sensibles en `lead_metadata` se encriptan en disco (AES-256).

---

## 2. Stack Tecnológico {#stack-tecnologico}

### 2.1 Frontend

| Tecnología | Versión | Rol |
|---|---|---|
| React | 18 | Framework UI |
| Vite | latest | Bundler y dev server |
| TypeScript | 5.x | Tipado estático |
| Zustand | latest | Estado global |
| React Router | v6 | Navegación |
| Radix UI | latest | Componentes accesibles |
| Recharts | latest | Gráficos |
| Tailwind CSS | v4 | Estilos |

### 2.2 Backend

| Tecnología | Versión | Rol |
|---|---|---|
| FastAPI | latest | API REST + WebSockets |
| Python | 3.11+ | Runtime |
| SQLAlchemy | 2.x (async) | ORM |
| PostgreSQL | 15 | Base de datos principal |
| pgvector | latest | Vectores para RAG (embeddings 768-dim) |
| Redis | latest | Cache + broker de Celery |
| Celery | latest | Cola de tareas asíncronas |
| Alembic | latest | Migraciones de BD |
| Python-multipart | latest | Upload de archivos |

### 2.3 LLMs

| Proveedor | Modelo | Rol |
|---|---|---|
| Google Gemini | 2.0 / 2.5 | LLM primario, embeddings (`text-embedding-004`) |
| Anthropic Claude | Sonnet 4 | Fallback primario |
| OpenAI | GPT-4o | Fallback secundario |
| Google Gemma | latest | Fast / tareas ligeras |

### 2.4 Voz y Calendario

| Servicio | Uso |
|---|---|
| VAPI | Llamadas de voz entrantes/salientes |
| Bland AI | Llamadas de voz alternativas |
| Google Calendar API | Scheduling de visitas |
| Microsoft Outlook | Scheduling alternativo |

### 2.5 Mensajería

| Canal | Mecanismo |
|---|---|
| WhatsApp | Webhook |
| Telegram | Webhook |
| Webchat | WebSocket |

### 2.6 Infraestructura

| Tecnología | Uso |
|---|---|
| Docker | Contenedores |
| Docker Compose | Orquestación local y despliegue |

---

## 3. Arquitectura General {#arquitectura-general}

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              USUARIO FINAL                                   │
│         ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│         │ WhatsApp │  │ Telegram │  │ Webchat  │  │  Voz     │            │
│         └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
└──────────────────────────┼────────────────┼─────────────┼───────────────────┘
                           │                │             │
                           ▼                ▼             ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            FASTAPI BACKEND                                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         Webhook / REST / WS                             │ │
│  │   POST /webhooks/telegram    GET /ws/{broker_id}   POST /webhooks/whatsapp │
│  └────────────────────────────┬────────────────────────────────────────────┘ │
│                               │                                              │
│  ┌────────────────────────────▼────────────────────────────────────────────┐ │
│  │                      ChatOrchestratorService                           │ │
│  │   1. Resolver lead (get/create)                                         │ │
│  │   2. Analizar sentimiento (heurística + LLM asíncrono via Celery)      │ │
│  │   3. AgentSupervisor.process()                                          │ │
│  │      └── Routing por stage → agente correspondiente                      │ │
│  │   4. LLMServiceFacade (Gemini → Claude → OpenAI)                        │ │
│  │   5. Broadcast WebSocket a frontend                                     │ │
│  └────────────────────────────┬────────────────────────────────────────────┘ │
│                               │                                              │
│            ┌─────────────────┼─────────────────┐                            │
│            ▼                 ▼                 ▼                            │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐               │
│  │  QualifierAgent │ │  SchedulerAgent │ │  FollowUpAgent  │               │
│  │  PropertyAgent  │ │                 │ │                 │               │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘               │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │  LLMServiceFacade  ──►  LLMRouter (primary + fallback, auto-failover)   │ │
│  │       ├── GeminiProvider                                                 │ │
│  │       ├── ClaudeProvider                                                 │ │
│  │       └── OpenAIProvider                                                 │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │                         Celery Workers                                   │ │
│  │  ├── sentiment_tasks    (análisis de sentimiento asíncrono)             │ │
│  │  ├── campaign_executor  (ejecución de campañas)                          │ │
│  │  ├── scoring_tasks      (re-score de leads)                              │ │
│  │  ├── telegram_tasks     (envío de mensajes)                              │ │
│  │  ├── voice_tasks        (llamadas VAPI)                                  │ │
│  │  └── dlq_tasks          (Dead Letter Queue: reintento / descarte)        │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   PostgreSQL     │    │      Redis       │    │   Google Calendar │
│   (pgvector)     │    │  (cache/broker)  │    │   / VAPI / etc.   │
└──────────────────┘    └──────────────────┘    └──────────────────┘
```

### 3.1 Decisiones de Diseño Clave

- **Dual-directory pattern en backend:** código nuevo bajo `app/features/` (vertical slices autonomy), código compartido/maduro bajo `app/routes/` y `app/services/`.
- **Tool-based handoffs entre agentes:** se eliminaron los regex frágil (`_WORD_KEYWORDS`). Ahora cada agente declara `_HANDOFF_TOOLS` y el LLM decide semánticamente cuándo transferir.
- **Semantic Cache:** cache de Redis con búsqueda de similitud coseno sobre mensajes sin PII para evitar repetir llamadas LLM con contenido idéntico.
- **Prompt Cache:** Gemini Context Cache para system prompts estáticos de cada broker (persona IA, few-shot examples).
- **DLQ (Dead Letter Queue):** todas las tareas Celery heredan de `DLQTask`. Cuando se agotan los reintentos, la tarea se mueve a la cola muerta para inspección manual.

---

## 4. Flujo de Datos {#flujo-de-datos}

### 4.1 Flujo Completo de un Mensaje entrante

```
1. Webhook received (Telegram / WhatsApp / Webchat)
      │
2. FastAPI endpoint valida firma + extrae broker_id
      │
3. ChatOrchestratorService.process_chat_message()
      │
      ├── 3.1 Lead resolution
      │         GET Lead by phone_number + broker_id
      │         └─► Si no existe → CREATE Lead (stage: "entrada")
      │
      ├── 3.2 Sentiment analysis (Celery async)
      │         ├─ Heurística rápida (palabras clave negativas)
      │         └─ LLM fallback si heurística inconclusive
      │
      ├── 3.3 AgentSupervisor.process(message, AgentContext, db)
      │         │
      │         ├─ _select_agent() → lookup _STAGE_TO_AGENT
      │         │     entrada/perfilamiento → QualifierAgent
      │         │     calificacion_financiera → SchedulerAgent
      │         │     agendado/seguimiento/referidos → FollowUpAgent
      │         │     entrada + property intent → PropertyAgent
      │         │
      │         ├─ Agent.run() → LLMServiceFacade con tools
      │         │
      │         └─ Si LLM llama handoff tool → capture HandoffSignal
      │               └─► AgentSupervisor.process() recursivo
      │
      ├── 3.4 LLMServiceFacade.analyze_lead_qualification() o
      │         generate_response_with_function_calling()
      │         ├─ Intent: GeminiProvider (primary)
      │         ├─ Fallback 1: ClaudeProvider
      │         └─ Fallback 2: OpenAIProvider
      │
      ├── 3.5 Response + tool execution
      │         ├─ Si hay tool_calls → tool_executor callback
      │         └─ Genera texto de respuesta al lead
      │
      ├── 3.6 Persist ChatMessage (provider, direction, message_text)
      │
      ├── 3.7 ws_manager.broadcast(broker_id, event)
      │         Tipos: new_message | stage_changed | lead_assigned | lead_hot | typing
      │
      └── 3.8 Celery: tasks según resultado
            ├─ SchedulingAgent → appointment creation → Google Calendar
            ├─ ScoringTasks → recalcular lead_score
            └─ CampaignTasks → avanzar campaign_step

4. HTTP 200 al provider (Telegram/WhatsApp)
```

### 4.2 Flujo de Llamada de Voz (VAPI)

```
Usuario llama → VAPI webhook → /webhooks/voice
  → voice_tasks.create_inbound_call() → verificar lead
  → agent对话 con lead (VAPI + LLM)
  → Al finalizar → guardar VoiceCall record
  → Celery: scoring_tasks.rescore_lead()
```

---

## 5. Estructura del Proyecto {#estructura-del-proyecto}

### 5.1 Backend — `backend/app/`

```
backend/app/
├── features/                  # Vertical slices (rutas + lógica de dominio)
│   ├── auth/                  # Registro/login JWT
│   ├── leads/                # CRUD de leads
│   ├── chat/                 # Routing de chat ( Thin → app/services/chat/)
│   ├── broker/               # BrokerConfig, Users, Brokers
│   │   ├── routes_config.py
│   │   ├── routes_users.py
│   │   └── routes_brokers.py
│   ├── appointments/         # Citas y calendario
│   ├── campaigns/            # Campañas de nurturing
│   ├── pipeline/             # Etapas del pipeline inmobiliario
│   ├── templates/            # Plantillas de mensajes
│   ├── telegram/             # Webhook Telegram
│   ├── voice/                # Integración VAPI/Bland
│   └── webhooks/             # Webhooks genéricos
│
├── routes/                   # Implementaciones共享
│   ├── ws.py                 # WebSocket endpoint (eventos por broker)
│   ├── knowledge_base.py     # RAG CRUD + pgvector search
│   ├── costs.py              # Analytics de costos LLM
│   ├── admin_tasks.py        # Endpoints admin DLQ
│   ├── health.py             # Health check
│   └── conversations.py      # Historial de conversaciones
│
├── services/                 # Toda la lógica de negocio por subdomain
│   ├── llm/
│   │   ├── base_provider.py          # LLMMessage (unified type)
│   │   ├── facade.py                  # LLMServiceFacade (single entry point)
│   │   ├── router.py                   # LLMRouter (failover primario→fallback)
│   │   ├── gemini_provider.py
│   │   ├── claude_provider.py
│   │   ├── openai_provider.py
│   │   ├── semantic_cache.py          # Redis cosine-similarity cache
│   │   └── prompt_cache.py            # Gemini Context Cache
│   │
│   ├── agents/
│   │   ├── supervisor.py              # AgentSupervisor (routing + handoffs)
│   │   ├── base_agent.py              # BaseAgent
│   │   ├── qualifier_agent.py         # entry + perfilamiento
│   │   ├── property_agent.py          # búsqueda de propiedades
│   │   ├── scheduler_agent.py         # agendado
│   │   └── follow_up_agent.py          # seguimiento + referidos
│   │
│   ├── chat/
│   │   ├── orchestrator.py            # ChatOrchestratorService
│   │   ├── state_machine.py           # ChatStateMachine
│   │   └── service.py                  # ChatService
│   │
│   ├── sentiment/
│   │   ├── heuristics.py
│   │   ├── scorer.py
│   │   └── escalation.py
│   │
│   ├── pipeline/
│   │   ├── constants.py               # PIPELINE_STAGES dict
│   │   ├── advancement.py
│   │   └── metrics.py
│   │
│   ├── leads/
│   │   ├── context.py                  # Lead context builder
│   │   ├── scoring.py
│   │   └── service.py
│   │
│   ├── broker/
│   │   └── config.py
│   │
│   ├── appointments/
│   │   └── service.py                  # Google Calendar + Outlook
│   │
│   ├── campaigns/
│   │   └── executor.py
│   │
│   └── voice/
│       └── service.py
│
├── core/
│   ├── config.py                # Settings (pydantic BaseSettings)
│   ├── encryption.py            # AES-256 para PII en lead_metadata
│   └── websocket_manager.py     # ws_manager singleton
│
├── tasks/                       # Tareas Celery (todas heredan DLQTask)
│   ├── base.py                  # DLQTask base class
│   ├── sentiment_tasks.py
│   ├── campaign_executor.py
│   ├── scoring_tasks.py
│   ├── telegram_tasks.py
│   ├── voice_tasks.py
│   └── dlq_tasks.py             # Reintento y descarte de DLQ
│
├── mcp/                         # FastMCP server (tools de appointments)
│   ├── server.py
│   └── adapter.py               # MCPClientAdapter (in-process)
│
├── models/                      # SQLAlchemy models
│   ├── lead.py
│   ├── broker.py
│   ├── chat_message.py
│   ├── appointment.py
│   ├── knowledge_base.py
│   ├── campaign.py
│   └── voice_call.py
│
└── schemas/                     # Pydantic schemas (request/response)
```

### 5.2 Frontend — `frontend/src/`

```
frontend/src/
├── app/
│   ├── App.tsx
│   └── router.tsx
│
├── features/
│   ├── auth/
│   ├── dashboard/
│   ├── leads/
│   ├── pipeline/
│   ├── campaigns/
│   ├── appointments/
│   ├── settings/
│   ├── users/
│   ├── brokers/
│   ├── llm-costs/
│   ├── chat/
│   ├── conversations/
│   ├── super-admin/
│   ├── observability/
│   └── properties/
│
├── shared/
│   ├── components/
│   │   └── layout/
│   ├── context/
│   ├── guards/
│   ├── lib/
│   └── types/
│
├── store/                       # Zustand stores
└── styles/
    └── globals.css
```

---

## 6. Modelos de Datos {#modelos-de-datos}

### 6.1 Lead

```
Lead
├── id: UUID (PK)
├── broker_id: UUID (FK → Broker)
├── phone_number: String          # Único por broker
├── name: String
├── email: String (nullable)
├── status: Enum (active, inactive, converted, lost)
├── lead_score: Integer           # 0-100
├── pipeline_stage: String        # FK → PIPELINE_STAGES
├── lead_metadata: JSONB          # Estado conversación, scoring components, PII encriptado
├── human_mode: Boolean           # Si True, deriva a agente humano
├── dicom_status: String         # "clean" | "dirty" | "unknown"
├── created_at: DateTime
└── updated_at: DateTime
```

### 6.2 Broker

```
Broker
├── id: UUID (PK)
├── name: String
├── slug: String (único)
├── plan_id: String
├── created_at: DateTime
└── settings: JSONB
```

### 6.3 ChatMessage

```
ChatMessage
├── id: UUID (PK)
├── lead_id: UUID (FK)
├── broker_id: UUID (FK)
├── provider: Enum (telegram, whatsapp, webchat)
├── direction: Enum (inbound, outbound)
├── message_text: Text
├── ai_response_used: Boolean
├── created_at: DateTime
└── metadata: JSONB
```

### 6.4 Appointment

```
Appointment
├── id: UUID (PK)
├── lead_id: UUID (FK)
├── agent_id: UUID (FK → User, nullable)
├── broker_id: UUID (FK)
├── start_time: DateTime
├── end_time: DateTime
├── status: Enum (scheduled, confirmed, cancelled, completed)
├── appointment_type: Enum (property_visit, call, video_call)
├── google_event_id: String (nullable)
├── notes: Text (nullable)
└── created_at: DateTime
```

### 6.5 KnowledgeBase

```
KnowledgeBase
├── id: UUID (PK)
├── broker_id: UUID (FK)
├── title: String
├── content: Text
├── source_type: String           # "pdf", "url", "manual"
├── embedding: Vector(768)       # pgvector, Gemini text-embedding-004
├── created_at: DateTime
└── updated_at: DateTime
```

### 6.6 Campaign y CampaignStep

```
Campaign
├── id: UUID (PK)
├── broker_id: UUID (FK)
├── name: String
├── status: Enum (draft, active, paused, completed)
├── start_date: Date
├── end_date: Date (nullable)
├── created_at: DateTime
└── steps: List[CampaignStep]

CampaignStep
├── id: UUID (PK)
├── campaign_id: UUID (FK)
├── step_order: Integer
├── message_template: Text
├── delay_days: Integer
├── trigger_condition: JSONB
└── status: Enum (pending, sent, failed)
```

### 6.7 VoiceCall

```
VoiceCall
├── id: UUID (PK)
├── lead_id: UUID (FK)
├── broker_id: UUID (FK)
├── provider: Enum (vapi, bland)
├── direction: Enum (inbound, outbound)
├── status: Enum (initiated, in_progress, completed, failed)
├── duration_seconds: Integer
├── recording_url: String (nullable)
├── transcript: Text (nullable)
├── created_at: DateTime
└── ended_at: DateTime (nullable)
```

---

## 7. Servicios Clave {#servicios-clave}

### 7.1 LLMServiceFacade (`app/services/llm/facade.py`)

Punto único de entrada para todas las llamadas LLM. Todos los métodos son estáticos (no se instancia).

```python
LLMServiceFacade.analyze_lead_qualification(message, lead_context, ...)
LLMServiceFacade.generate_response_with_function_calling(system_prompt, contents, tools, tool_executor, tool_mode_override, ...)
LLMServiceFacade.build_llm_prompt(broker_id, lead_context, ...)
```

Delegación interna:

```
LLMServiceFacade
  └── get_llm_provider()
          └── LLMRouter (primary + fallback)
                  ├── GeminiProvider
                  ├── ClaudeProvider
                  └── OpenAIProvider
```

**Failover:** si `GeminiProvider.generate()` lanza error transitorio, `LLMRouter` prueba `ClaudeProvider` → luego `OpenAIProvider`. Errores permanentes se propagan.

**Function Calling:**
- `LLMToolDefinition`: formato unificado de tool (name, description, parameters JSON Schema).
- `tool_executor`: callback async invocado por cada tool call. Los agentes implementan la lógica.
- `tool_mode_override`: `"ANY"` (forzar function calling) o `"AUTO"` (el LLM decide). Pass-through a `GeminiProvider.generate_with_tools()`.

### 7.2 ChatOrchestratorService (`app/services/chat/orchestrator.py`)

Orquesta todo el pipeline de un mensaje entrante. Coordina lead resolution → sentiment → agente → LLM → persistencia → WebSocket broadcast.

### 7.3 AgentSupervisor (`app/services/agents/supervisor.py`)

Selecciona el agente correcto según `pipeline_stage` del lead y managea handovers.

- `_STAGE_TO_AGENT`: lookup determinista stage → tipo de agente.
- Si `current_agent` está seteado en el lead, permanece en ese agente hasta que este indique handover.
- Handover vía `HandoffSignal` (tool-based, no keyword-based).

### 7.4 Semantic Cache (`app/services/llm/semantic_cache.py`)

Cache Redis con similitud coseno sobre embeddings. Solo almacena mensajes sin PII. Skip LLM call si similar message ya fue cacheado.

### 7.5 Prompt Cache (`app/services/llm/prompt_cache.py`)

Gemini Context Cache para system prompts estáticos de broker (persona IA, few-shot examples, instrucciones DICOM). Evita re-enviar prompts grandes en cada request.

### 7.6 WebSocketManager (`app/core/websocket_manager.py`)

Singleton `ws_manager` que mantiene conexiones WebSocket por `broker_id`. Tipos de evento broadcast:

| Evento | Payload |
|---|---|
| `new_message` | ChatMessage |
| `stage_changed` | lead_id, old_stage, new_stage |
| `lead_assigned` | lead_id, agent_id |
| `lead_hot` | lead_id, score |
| `typing` | broker_id, is_typing |

### 7.7 BrokerConfigService (`app/services/broker/config.py`)

Carga y cachea `BrokerPromptConfig` por broker (persona IA, system prompt, few-shot examples, instrucciones DICOM).

---

## 8. Agentes Multi-IA {#agentes-multi-ia}

### 8.1 Tabla de Agentes

| Agente | Stages | Responsabilidad |
|---|---|---|
| **QualifierAgent** | `entrada`, `perfilamiento` | Identificar intención de compra/venta, gathers datos financieros |
| **PropertyAgent** | `entrada`, `perfilamiento` | Búsqueda de propiedades por intención del lead |
| **SchedulerAgent** | `calificacion_financiera` | Agendar visitas, confirmar datos de contacto |
| **FollowUpAgent** | `agendado`, `seguimiento`, `referidos` | Follow-up post-visita, solicitar referidos, re-agendar |

### 8.2 Routing Inicial

```
AgentSupervisor._select_agent()
│
└── _STAGE_TO_AGENT:
    entrada         → QualifierAgent (default) o PropertyAgent (si property intent)
    perfilamiento   → QualifierAgent (default) o PropertyAgent (si property intent)
    calificacion_financiera → SchedulerAgent
    agendado        → FollowUpAgent
    seguimiento     → FollowUpAgent
    referidos       → FollowUpAgent
```

### 8.3 Mecanismo de Handover

1. Cada agente declara `_HANDOFF_TOOLS` (tool definitions como `handoff_to_scheduler`, `handoff_to_follow_up`, etc.).
2. En `run()`, el agente invoca `LLMServiceFacade.generate_response_with_tools()` con esas tools.
3. Si el LLM determina que es momento de transferir, llama el tool correspondiente.
4. El `tool_executor` captura el intent en `_handoff_intent` → construye `HandoffSignal`.
5. `AgentSupervisor.process()` se llama recursivamente con el nuevo agente.

### 8.4 Regla DICOM

> **Nunca prometer crédito pre-aprobación, financiamiento o "pre-aprobación" a un lead con `dicom_status == "dirty"`.**

`QualifierAgent` verifica DICOM antes de generar cualquier promesa de financiamiento. Si DICOM está dirty, no emite handoff a `SchedulerAgent` y responde con mensaje genérico.

---

## 9. Integraciones Externas {#integraciones-externas}

### 9.1 Telegram

- **Inbound:** `POST /webhooks/telegram` recibe updates.
- **Outbound:** `celery: telegram_tasks.send_message` envía mensajes.
- Auth: Bot Token en headers.

### 9.2 WhatsApp

- **Inbound:** `POST /webhooks/whatsapp` recibe mensajes.
- **Outbound:** API de WhatsApp Business.
- Auth: Webhook verification token.

### 9.3 VAPI (Voice)

- **Inbound:** `POST /webhooks/voice` recibe eventos de llamada.
- **Outbound:** `celery: voice_tasks.create_outbound_call`.
- Config: `VAPI_ID`, `VAPI_KEY`, `VAPI_WEBHOOK_URL`.

### 9.4 Bland AI

- Fallback para llamadas de voz.
- Misma interfaz que VAPI via `VoiceService`.

### 9.5 Google Calendar

- OAuth2 con credenciales de service account.
- `AppointmentService.create_calendar_event()` → `google_calendar.insert_event()`.
- Sync bidireccional: cambios en calendario actualizan `Appointment.status`.

### 9.6 Microsoft Outlook

- Similar a Google Calendar via `microsoftgraph` SDK.
- Configurado por broker en `Broker.settings`.

### 9.7 Gemini (Embeddings / RAG)

- `text-embedding-004` (768-dim) para vectorizar contenido de `KnowledgeBase`.
- Búsqueda: `KnowledgeBaseService.semantic_search(query, broker_id, top_k=5)`.
- PostgreSQL + pgvector: `embedding <-> query_embedding` (cosine distance).

---

## 10. Multi-Tenancy {#multi-tenancy}

### 10.1 Aislamiento

- **Cada tabla con datos de usuario tiene `broker_id` FK.** Queries siempre filtran por `broker_id`.
- El middleware JWT extrae `broker_id` del token y lo inyecta en `request.state`.
- RLS (Row Level Security) no se usa; el ORM filtra a nivel de aplicación.

### 10.2 BrokerPromptConfig

```
BrokerPromptConfig (por broker)
├── broker_id: UUID (FK)
├── ai_persona: String          # "Sofía", "Carlos", etc.
├── system_prompt: Text
├── few_shot_examples: JSONB
├── dicom_instructions: Text
└── temperature: Float
```

### 10.3 Planes

| Plan | Límites |
|---|---|
| Free | 50 leads, 1 agente |
| Pro | 500 leads, 3 agentes |
| Enterprise | leads ilimitados, agentes ilimitados |

---

## 11. Changelog {#changelog}

| Fecha | Cambio |
|---|---|
| 2026-04-17 | Creación del documento de arquitectura |
| 2026-04-17 | Documentación del stack: React 18 + Vite + Zustand (frontend), FastAPI + SQLAlchemy async + PostgreSQL 15 + pgvector (backend) |
| 2026-04-17 | Documentación del flujo completo de mensajes entrantes: webhook → ChatOrchestrator → AgentSupervisor → LLMServiceFacade → WebSocket broadcast |
| 2026-04-17 | Detalle de agentes: QualifierAgent, PropertyAgent, SchedulerAgent, FollowUpAgent con routing basado en stages |
| 2026-04-17 | Documentación del mecanismo tool-based handoffs (reemplazo de keyword-based routing) |
| 2026-04-17 | Detalle de LLM Router: Gemini (primary) → Claude (fallback 1) → OpenAI (fallback 2) con failover automático |
| 2026-04-17 | Documentación de Semantic Cache (Redis cosine-similarity) y Prompt Cache (Gemini Context Cache) |
| 2026-04-17 | Detalle de multi-tenancy: filtro obligatorio por broker_id en todas las queries |
| 2026-04-17 | Documentación de integraciones externas: Telegram, WhatsApp, VAPI, Bland AI, Google Calendar, Outlook, Gemini embeddings |
| 2026-04-17 | Detalle de modelos de datos: Lead, Broker, ChatMessage, Appointment, KnowledgeBase, Campaign, VoiceCall |
| 2026-04-17 | Documentación de Celery tasks y DLQ (Dead Letter Queue) |
| 2026-04-17 | Detalle de WebSocket events: new_message, stage_changed, lead_assigned, lead_hot, typing |
| 2026-04-17 | Regla DICOM documentada: nunca prometer pre-aprobación a leads con dicom_status == "dirty" |
