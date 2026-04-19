# Arquitectura Completa — CRM Inmobiliario "AI Lead Agent Pro"

> Documento generado el 2 de abril 2026. Contiene toda la implementación real del sistema con fragmentos de código, esquemas de BD y flujos detallados.

---

## 1. STACK TECNOLÓGICO

### 1.1 Frontend

| Categoría | Tecnología | Versión |
|---|---|---|
| **Framework** | React | 18.2.0 |
| **Build Tool** | Vite + SWC | 5.0.8 |
| **Lenguaje** | TypeScript | 5.9.3 |
| **Estado Global** | Zustand | 4.4.7 |
| **HTTP Client** | Axios | 1.6.2 |
| **Routing** | React Router DOM | 6.20.0 |
| **UI Primitives** | Radix UI | (avatar, checkbox, dialog, dropdown, label, popover, progress, select, separator, switch, tabs, tooltip) |
| **Styling** | Tailwind CSS | 3.3.6 |
| **Tablas** | TanStack React Table | 8.21.3 |
| **Gráficos** | Recharts | 3.5.0 |
| **Drag & Drop** | dnd-kit | latest |
| **Iconos** | Lucide React | 0.575.0 |
| **Toast** | Sonner | 2.0.7 |
| **Testing** | Vitest + Testing Library | 4.0.18 |
| **Linting** | ESLint + Prettier | 9.39.3 / 3.8.1 |

**Estructura de carpetas:**
```
frontend/src/
├── app/          → App.tsx, router.tsx
├── features/     → auth, dashboard, leads, pipeline, campaigns,
│                   appointments, settings, users, brokers,
│                   llm-costs, chat, conversations
├── shared/       → components/layout, context, guards, lib, types
├── store/        → Zustand stores globales
└── styles/       → globals.css (Tailwind)
```

**Stores Zustand:**
- **`useAuthStore`** — JWT token, user data, roles (`SUPERADMIN | ADMIN | AGENT`), localStorage persistence
- **`WebSocketContext`** — Provider que envuelve las rutas protegidas, maneja conexión WS por `broker_id`

**Dev Proxy (Vite):**
```typescript
proxy: {
  '/api':  { target: 'http://localhost:8000', changeOrigin: true },
  '/auth': { target: 'http://localhost:8000', changeOrigin: true },
}
```

**Code Splitting (6 chunks):**
```typescript
manualChunks: {
  'vendor-react':  ['react', 'react-dom', 'react-router-dom'],
  'vendor-ui':     ['@radix-ui/*'],
  'vendor-charts': ['recharts', 'react-is'],
  'vendor-table':  ['@tanstack/react-table'],
  'vendor-dnd':    ['@dnd-kit/*'],
  'vendor-utils':  ['axios', 'zustand', 'sonner', 'lucide-react', 'clsx', 'tailwind-merge'],
}
```

**Lazy Loading:** Todas las páginas se cargan con `React.lazy()` + `Suspense`.

**Guards:**
- `AuthGuard` — redirige a `/login` si no hay token
- `RoleGuard` — restringe por `allowedRoles` (ej: campañas solo para admin/superadmin)

---

### 1.2 Backend

| Categoría | Tecnología |
|---|---|
| **Lenguaje** | Python 3.11 |
| **Framework** | FastAPI (async) |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Migraciones** | Alembic |
| **Task Queue** | Celery + Redis (broker) |
| **Server** | Uvicorn |
| **Auth** | JWT (python-jose / passlib bcrypt) |

**Estructura del backend:**
```
backend/app/
├── features/       → Vertical slices (auth, leads, chat, broker,
│                     appointments, campaigns, pipeline, templates,
│                     telegram, voice, webhooks)
├── routes/         → ws.py, knowledge_base.py, costs.py, admin_tasks.py,
│                     health.py, conversations.py
├── services/       → Business logic por dominio
│   ├── llm/        → Providers (Gemini, Claude, OpenAI), facade, router, caches
│   ├── agents/     → Multi-agent system (Supervisor, Qualifier, Scheduler, FollowUp)
│   ├── chat/       → Orchestrator, ChatService, providers por canal
│   ├── sentiment/  → Heurísticas, scorer, escalation
│   ├── pipeline/   → Stages, advancement, metrics
│   ├── leads/      → Context, scoring
│   ├── broker/     → Config
│   ├── appointments/ → Google Calendar integration
│   ├── campaigns/  → Campaign execution
│   └── voice/      → VAPI voice calls
├── models/         → SQLAlchemy models
├── core/           → Config, encryption, websocket_manager
├── tasks/          → Celery tasks + DLQ
└── mcp/            → MCP server (appointment tools)
```

---

### 1.3 Base de Datos

**Motor:** PostgreSQL con extensión **pgvector** (embeddings 768-dim)

**Tablas principales:**

```
┌──────────────────────┐     ┌──────────────────────────┐
│ brokers              │     │ users                    │
│──────────────────────│     │──────────────────────────│
│ id (PK)              │◄────│ broker_id (FK)           │
│ name                 │     │ email (UNIQUE)           │
│ slug (UNIQUE)        │     │ hashed_password          │
│ contact_phone        │     │ name                     │
│ contact_email        │     │ role (SUPERADMIN|ADMIN|  │
│ business_hours       │     │        AGENT)            │
│ service_zones (JSONB)│     │ google_calendar_id       │
│ is_active            │     │ google_calendar_connected│
└──────────┬───────────┘     └──────────────────────────┘
           │
           │ 1:1
┌──────────▼───────────┐     ┌──────────────────────────┐
│ broker_prompt_configs│     │ broker_lead_configs       │
│──────────────────────│     │──────────────────────────│
│ broker_id (FK,UNIQUE)│     │ broker_id (FK,UNIQUE)    │
│ agent_name           │     │ field_weights (JSONB)    │
│ agent_role           │     │ cold_max_score           │
│ identity_prompt      │     │ warm_max_score           │
│ business_context     │     │ hot_min_score            │
│ agent_objective      │     │ field_priority (JSONB)   │
│ data_collection_prompt│    │ scoring_config (JSONB)   │
│ behavior_rules       │     │ alert_on_hot_lead        │
│ restrictions         │     │ alert_score_threshold    │
│ situation_handlers   │     └──────────────────────────┘
│  (JSONB)             │
│ output_format        │     ┌──────────────────────────┐
│ full_custom_prompt   │     │ broker_chat_configs      │
│ enable_appointment_  │     │──────────────────────────│
│  booking             │     │ broker_id (FK,UNIQUE)    │
│ tools_instructions   │     │ provider_configs (JSONB) │
│ benefits_info (JSONB)│     │  → whatsapp.phone_number_│
│ qualification_       │     │    id, api_token         │
│  requirements (JSONB)│     │  → telegram.bot_token    │
│ follow_up_messages   │     └──────────────────────────┘
│  (JSONB)             │
│ additional_fields    │
│  (JSONB)             │
│ meeting_config(JSONB)│
│ message_templates    │
│  (JSONB)             │
│ google_refresh_token │
│  (encrypted)         │
│ google_calendar_id   │
│ google_calendar_email│
└──────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ leads                                                        │
│──────────────────────────────────────────────────────────────│
│ id (PK)              │ phone (VARCHAR 20, INDEXED)           │
│ name                 │ email                                 │
│ status (cold|warm|hot|converted|lost)    INDEXED             │
│ lead_score (Float)                       INDEXED             │
│ lead_score_components (JSON)                                 │
│ last_contacted (DateTime TZ)             INDEXED             │
│ pipeline_stage (VARCHAR 50)              INDEXED             │
│   → entrada|perfilamiento|calificacion_financiera|           │
│     potencial|agendado|ganado|perdido                        │
│ stage_entered_at (DateTime TZ)           INDEXED             │
│ campaign_history (JSON)                                      │
│ assigned_to (FK → users.id)              INDEXED             │
│ broker_id (FK → brokers.id)              INDEXED             │
│ treatment_type (enum)                    INDEXED             │
│ next_action_at (DateTime TZ)             INDEXED             │
│ close_reason, close_reason_detail, closed_at, closed_from_   │
│  stage                                                       │
│ notes (Text)                                                 │
│ tags (JSON)  → ["inmobiliario", "activo"]                    │
│ lead_metadata (JSONB, column="metadata")                     │
│   → {                                                        │
│       budget, timeline, location, property_type, bedrooms,   │
│       bathrooms, parking, garden, square_meters,             │
│       max_price, min_price, salary, dicom_status,            │
│       morosidad_amount, current_agent, conversation_state,   │
│       interest_confirmed, interest_confirmed_at,             │
│       human_mode (bool),                                     │
│       human_assigned_to (int),                               │
│       human_taken_at (ISO string),                           │
│       human_mode_notified (bool),                            │
│       sentiment: {                                           │
│         frustration_score, message_scores[], tone_hint,      │
│         escalated, escalated_at                              │
│       }                                                      │
│     }                                                        │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ chat_messages                                                │
│──────────────────────────────────────────────────────────────│
│ id (PK)                                                      │
│ lead_id (FK → leads.id)                  INDEXED             │
│ broker_id (FK → brokers.id)              INDEXED             │
│ provider (enum: telegram|whatsapp|instagram|facebook|tiktok| │
│           webchat)                       INDEXED             │
│ channel_user_id (VARCHAR 255)            INDEXED             │
│ channel_username                                             │
│ channel_message_id                       INDEXED             │
│ message_text (Text)                                          │
│ direction (enum: in|out)                                     │
│ status (enum: pending|sent|delivered|read|failed)            │
│ provider_metadata (JSONB)                                    │
│ attachments (JSONB)                                          │
│ ai_response_used (Boolean, default=True)                     │
│ prompt_version_id (FK → prompt_versions.id)                  │
│──────────────────────────────────────────────────────────────│
│ Índices compuestos:                                          │
│   (lead_id, provider), (broker_id, provider),                │
│   (provider, channel_user_id)                                │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ knowledge_base (pgvector)                                    │
│──────────────────────────────────────────────────────────────│
│ id (PK)                                                      │
│ broker_id (FK → brokers.id)              INDEXED             │
│ title (VARCHAR 255)                                          │
│ content (Text)                                               │
│ embedding (Vector 768)  → Gemini text-embedding-004          │
│ source_type (property|faq|policy|subsidy|custom)             │
│ kb_metadata (JSONB) → price, location, bedrooms, amenities   │
│──────────────────────────────────────────────────────────────│
│ Índice IVFFlat cosine_ops, lists=100                         │
│ Índice compuesto: (broker_id, source_type)                   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────┐  ┌──────────────────────────┐
│ appointments             │  │ voice_calls              │
│──────────────────────────│  │──────────────────────────│
│ lead_id (FK)             │  │ lead_id (FK)             │
│ agent_id (FK → users.id) │  │ broker_id (FK)           │
│ appointment_type (enum)  │  │ status (enum: initiated| │
│ status (enum: scheduled| │  │   ringing|answered|      │
│   confirmed|cancelled|   │  │   completed|failed|      │
│   completed|no_show)     │  │   no_answer|busy|        │
│ start_time (DateTime TZ) │  │   cancelled)             │
│ end_time                 │  │ call_duration            │
│ google_event_id          │  │ vapi_call_id             │
│ notes                    │  │ transcripts []           │
└──────────────────────────┘  └──────────────────────────┘
```

---

### 1.4 Servicios Externos

| Servicio | Uso | Integración |
|---|---|---|
| **Google Gemini** | LLM principal (chat, análisis, embeddings) | SDK `google-generativeai`, Context Caching |
| **Anthropic Claude** | LLM fallback | SDK `anthropic` |
| **OpenAI** | LLM fallback + eval judge | SDK `openai` |
| **VAPI** | Llamadas de voz automatizadas | API REST |
| **Telegram Bot API** | Canal de mensajería | `python-telegram-bot` |
| **WhatsApp Cloud API** | Canal de mensajería | API REST (Meta) |
| **Google Calendar** | Agendamiento de citas | OAuth2 + Calendar API |
| **Redis** | Cache semántico, broker Celery, DLQ, prompt cache | `redis-py` async |
| **Equifax/DICOM** | Verificación crediticia (referencia) | Manual (lead reporta) |

---

### 1.5 Infraestructura

**Docker Compose (desarrollo):**
```yaml
services:
  backend:     FastAPI (uvicorn --reload)
  frontend:    Vite dev server
  db:          PostgreSQL 15 + pgvector
  redis:       Redis 7
  celery:      Celery worker
  celery-beat: Celery beat (tareas periódicas)
```

**Producción:**
- **Backend:** Render (render.yaml) — Web Service
- **Frontend:** Vercel (vercel.json) — SPA con rewrites a `/index.html`
- **BD:** PostgreSQL managed (Render)
- **Redis:** Redis managed (Render)
- **CI/CD:** No hay GitHub Actions configurado actualmente

---

## 2. ARQUITECTURA DEL AGENTE IA

### 2.1 Modelos de IA y Consumo

**Capa de abstracción multi-provider:**

```
LLMServiceFacade  ← punto de entrada único (métodos estáticos)
    └── get_llm_provider()
            └── LLMRouter (primary + fallback, auto-failover)
                    ├── GeminiProvider   ← default primario
                    ├── ClaudeProvider   ← fallback
                    └── OpenAIProvider   ← fallback
```

**LLMRouter** implementa circuit breaker + retry con backoff exponencial:
- **3 intentos** en provider primario (backoff 0.5s → 4.0s)
- **Errores retriable:** timeout, rate limit, 5xx, `ServiceUnavailable`, `ResourceExhausted`
- **Circuit breaker:** abre circuito si el provider falla consistentemente
- **Fallback automático:** si el primario falla, redirige al secundario

**Métodos principales del Facade:**

```python
class LLMServiceFacade:
    @staticmethod
    async def analyze_lead_qualification(message, lead_context, broker_id, lead_id) -> dict:
        """Extrae datos estructurados: name, phone, email, salary, location,
        dicom_status, morosidad_amount, interest_level, qualified, score_delta"""

    @staticmethod
    async def generate_response_with_function_calling(
        system_prompt, contents, tools, tool_executor, ...
    ) -> (str, list):
        """Genera respuesta con function calling (hasta 5 iteraciones).
        Soporta Gemini Context Caching para system prompts estáticos."""

    @staticmethod
    async def build_llm_prompt(lead_context, new_message, db, broker_id) -> tuple:
        """Construye (full_system_prompt, messages, static_system_prompt).
        Incluye RAG (top-3 chunks de knowledge_base), resumen de contexto,
        historial de conversación previo."""
```

---

### 2.2 Manejo de Contexto/Memoria

**El contexto se construye por cada mensaje a partir de:**

1. **Datos del lead** (`lead_metadata` JSONB): nombre, teléfono, email, ubicación, salario, DICOM, etc.
2. **Historial de mensajes** (`chat_messages` tabla): últimos N mensajes ordenados por fecha
3. **RAG semántico** (`knowledge_base` tabla): top-3 chunks relevantes por cosine similarity (pgvector)
4. **Estado del state machine** (`conversation_state` en metadata): GREETING, INTEREST_CHECK, DATA_COLLECTION, FINANCIAL_QUAL, SCHEDULING, COMPLETED
5. **Pipeline stage** (`pipeline_stage` columna): entrada → perfilamiento → calificacion_financiera → agendado → etc.
6. **Sentiment** (`sentiment` en metadata): frustration_score, tone_hint, escalated

**No hay memoria de largo plazo tipo vector store de conversaciones.** El contexto se reconstruye cada vez desde la BD.

**Resumen de contexto inyectado al LLM:**
```python
def _build_context_summary(lead_context, new_message):
    # Campos ya recopilados: nombre, teléfono, email, ubicación, salario, DICOM
    # Campos pendientes: los que faltan de la lista anterior
    # Historial: se convierte a formato LLMMessage [{role, content}, ...]
```

**Caches:**
- **Semantic Cache** (Redis): cachea respuestas LLM por similitud coseno del input. Skippea mensajes con PII.
- **Prompt Cache** (Gemini Context Cache): cachea el system prompt estático del broker para reducir tokens.

---

### 2.3 System Prompt / Instrucciones del Agente

El system prompt se compone de **secciones configurables por broker** (`BrokerPromptConfig`):

```
1. IDENTIDAD: agent_name ("Sofía"), agent_role ("asesora inmobiliaria")
2. CONTEXTO: business_context (info del broker)
3. OBJETIVO: agent_objective
4. RECOLECCIÓN DE DATOS: data_collection_prompt
5. REGLAS DE COMPORTAMIENTO: behavior_rules
6. RESTRICCIONES: restrictions
7. SITUACIONES ESPECIALES: situation_handlers (JSONB)
8. FORMATO DE SALIDA: output_format
```

**Reglas compartidas hardcodeadas:**
```python
TONE_GUIDELINES = "Español chileno, profesional pero cálido, máx 2-3 oraciones,
                   agrupar preguntas relacionadas (máx 3 por turno)"

DICOM_RULE = """
Pregunta: "¿Estás en DICOM o tienes deudas morosas?"
- "No" → dicom_status="clean", nunca preguntar monto de deuda
- "Sí" → preguntar monto; < $500K: continuar; > $500K: sugerir regularizar
- "No sé" → sugerir revisar equifax.cl / dicom.cl
Con DICOM activo: NUNCA usar "aprobado", "pre-aprobado" ni prometer crédito
"""

SALARY_RULE = "Siempre preguntar SUELDO/RENTA mensual, NUNCA presupuesto o precio."

CONTEXT_AWARENESS_RULE = "Leer datos recopilados antes de responder.
                          NUNCA preguntar datos ya en contexto."
```

Si `full_custom_prompt` está definido en `BrokerPromptConfig`, **reemplaza todas las secciones**.

---

### 2.4 Decisión: ¿Cuándo Responde la IA vs. Cuándo No?

```python
# En ChatOrchestratorService.process_chat_message():

# 1. SANITIZACIÓN — rechaza input malicioso
sanitize_chat_input(message, source=provider_name)
# → Lanza InputSanitizationError si es rechazado

# 2. HUMAN MODE CHECK — la IA se silencia completamente
if (lead.lead_metadata or {}).get("human_mode"):
    # → Primera vez: envía mensaje de handoff configurable
    # → Después: retorna "[human_mode]" (no se envía al cliente)
    return

# 3. PROCESAMIENTO NORMAL — la IA responde siempre
# El multi-agent system decide QUÉ responder, no SI responder
```

**La IA SIEMPRE responde** salvo que:
- `human_mode == True` en `lead_metadata` (un humano tomó control)
- El input falle la sanitización

---

### 2.5 Flujo Completo: Mensaje → Respuesta

```
📱 Telegram/WhatsApp/Webchat
       │
       ▼
┌─────────────────────────────────────────┐
│ 1. Webhook/API recibe mensaje           │
│    (features/telegram, webhooks,        │
│     features/chat)                      │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│ 2. ChatOrchestratorService              │
│    .process_chat_message()              │
│                                         │
│  a) sanitize_chat_input()               │
│  b) Get/Create Lead                     │
│  c) Log inbound message (ChatMessage)   │
│  d) CHECK: human_mode? → STOP           │
│  e) WS broadcast: "new_message"         │
│  f) WS broadcast: "typing" = true       │
│  g) ConversationStateMachine.from_lead  │
│  h) LeadContextService.get_lead_context │
│  i) LLMServiceFacade                    │
│     .analyze_lead_qualification()       │
│  j) Update lead_score (atomic SQL)      │
│  k) Update lead fields + metadata       │
│  l) Interest confirmation detection     │
│  m) Status update (COLD/WARM/HOT)       │
│  n) PipelineService.auto_advance_stage  │
│  o) Cache invalidation                  │
│  p) ─────────── MULTI-AGENT ──────────  │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│ 3. AgentSupervisor.process()            │
│                                         │
│  a) _select_agent(context):             │
│     - Sticky: current_agent primero     │
│     - Prioridad: FollowUp > Scheduler   │
│       > Qualifier                       │
│  b) agent.process(message, context, db) │
│  c) Apply context_updates               │
│  d) Check handoff signal                │
│  e) Si handoff: apply, break            │
│     (máx 3 hops de seguridad)           │
│  f) Return AgentResponse                │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│ 4. Post-processing (Orchestrator)       │
│                                         │
│  a) Persist current_agent en metadata   │
│  b) Log outbound message (ChatMessage,  │
│     ai_response_used=True)              │
│  c) WS broadcast: "typing" = false      │
│  d) WS broadcast: "ai_response"         │
│  e) Celery task: analyze_sentiment      │
│     (async, non-blocking)               │
│  f) Return ChatResult                   │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│ 5. Envío de respuesta al canal          │
│                                         │
│  - Telegram: bot.send_message()         │
│  - WhatsApp: WhatsAppService            │
│    .send_text_message()                 │
│  - Webchat: retorno HTTP directo        │
└─────────────────────────────────────────┘
```

---

## 3. HANDOFF IA ↔ HUMANO

### 3.1 ¿Cómo se Detecta que se Necesita Intervención Humana?

Hay **dos mecanismos**:

#### A) Automático — Análisis de Sentimiento

```python
# backend/app/services/sentiment/heuristics.py
# Analizador heurístico de keywords/patrones (costo LLM = 0)

_ABANDONMENT_PATTERNS = [
    (r"me voy.*otra|otro|competencia", 0.9, "abandonment_threat"),
    (r"buscaré.*otra inmobiliaria|corredor",  0.85, "abandonment_threat"),
    (r"no me interesa más",                    0.80, "abandonment_threat"),
    (r"olvídalo",                              0.75, "abandonment_threat"),
    (r"ya no|basta|hasta aquí|me cansé",       0.65, "abandonment_threat"),
    (r"mala experiencia|pésimo servicio",       0.70, "abandonment_threat"),
    ...
]

_FRUSTRATION_PATTERNS = [
    (r"estoy enojado|molesto|frustrado|harto", 0.75, "frustration"),
    (r"qué lata|qué fome|qué penca",          0.40, "frustration"),  # chilenismos
    (r"conchetumare|ctm|weon|chucha|puta",     0.85, "anger"),        # profanidad chilena
    (r"quiero hablar con.*jefe|supervisor",     0.80, "escalation_demand"),
    ...
]

_SARCASM_MARKERS = [
    (r"claro\.{2,}",          "sarcasm"),  # "claro..." (dismissive)
    (r"sí, seguro|sí, claro", "sarcasm"),
    ...
]

_POSITIVE_PATTERNS = [
    (r"gracias|perfecto|de acuerdo", -0.15),  # baja el score
    (r"me interesa|me gusta",        -0.20),
    ...
]
```

```python
# backend/app/services/sentiment/scorer.py
# Sliding-window con decay exponencial

ActionLevel:
  NONE        → score < 0.4 (no hacer nada)
  ADAPT_TONE  → 0.4 ≤ score < 0.7 (Sofía usa tono más empático)
  ESCALATE    → score ≥ 0.7 (pausar Sofía, notificar broker)

# Ventana deslizante de 3 mensajes con pesos exponenciales:
weights = [0.5^1, 0.5^2, 0.5^3]  # normalizado
# Mensaje más reciente pesa más
```

```python
# backend/app/services/sentiment/escalation.py
async def _escalate(db, lead_id, broker_id, sentiment, last_message, channel):
    # 1. Marca en BD: human_mode=True + sentiment.escalated=True
    await db.execute(text("""
        UPDATE leads SET metadata = jsonb_set(
            jsonb_set(COALESCE(metadata,'{}'), '{sentiment}', :sentiment, true),
            '{human_mode}', 'true', true
        ) WHERE id = :lead_id
    """))

    # 2. Broadcast WebSocket "lead_frustrated"
    await ws_manager.broadcast(broker_id, "lead_frustrated", {
        "lead_id": lead_id,
        "lead_name": lead_name,
        "frustration_score": score,
        "emotions": ["abandonment_threat", "frustration"],
        "last_message": last_message[:300],
        "channel": channel,
        "assigned_to": assigned_to,
    })
```

#### B) Manual — El Humano Toma Control desde el Dashboard

```python
# backend/app/routes/conversations.py

@router.post("/leads/{lead_id}/takeover")
async def takeover_lead(lead_id, db, current_user):
    """Human agent takes control — silences AI."""
    meta = dict(lead.lead_metadata or {})
    meta["human_mode"] = True
    meta["human_assigned_to"] = user_id
    meta["human_taken_at"] = datetime.now(UTC).isoformat()
    lead.lead_metadata = meta
    await db.commit()

    # Notifica en tiempo real a todos los dashboards del broker
    await ws_manager.broadcast(broker_id, "human_mode_changed", {
        "lead_id": lead_id,
        "human_mode": True,
        "taken_by": user_id,
    })
```

---

### 3.2 ¿Qué Pasa Cuando el Humano Toma Control?

**La IA se apaga COMPLETAMENTE.** No sugiere, no procesa, no analiza.

```python
# En ChatOrchestratorService.process_chat_message():

if (lead.lead_metadata or {}).get("human_mode"):
    meta = lead.lead_metadata or {}

    # Broadcast para que el frontend muestre el mensaje entrante
    await ws_manager.broadcast(broker_id, "human_mode_incoming", {
        "lead_id": lead.id,
        "lead_name": lead.name or lead.phone,
        "message_text": message[:300],
        "channel": provider_name,
        "assigned_to": meta.get("human_assigned_to"),
    })

    # PRIMERA VEZ: envía mensaje de handoff al cliente
    if not meta.get("human_mode_notified"):
        handoff_message = broker_templates.get("escalation_handoff",
            "Entiendo tu frustración. Un agente de nuestra inmobiliaria "
            "se pondrá en contacto contigo muy pronto para ayudarte "
            "personalmente. 🙏"
        )
        # Marca como notificado para no repetir
        UPDATE leads SET metadata = jsonb_set(..., '{human_mode_notified}', 'true')
        return ChatResult(response=handoff_message, ...)

    # MENSAJES SIGUIENTES: la IA NO responde nada
    return ChatResult(response="[human_mode]", ...)
    # "[human_mode]" es un sentinel — el caller NO lo envía al cliente
```

---

### 3.3 ¿Cómo Sabe el Humano que Debe Intervenir?

**Tres mecanismos de notificación:**

1. **WebSocket `lead_frustrated`** — cuando el sentiment scorer detecta escalación automática:
   ```json
   {"event": "lead_frustrated", "data": {
     "lead_id": 42,
     "lead_name": "Juan Pérez",
     "frustration_score": 0.82,
     "emotions": ["abandonment_threat", "frustration"],
     "last_message": "Me voy a buscar otra inmobiliaria, esto es terrible",
     "channel": "whatsapp",
     "assigned_to": 5
   }}
   ```

2. **WebSocket `human_mode_incoming`** — cuando llega un mensaje de un lead en human_mode:
   ```json
   {"event": "human_mode_incoming", "data": {
     "lead_id": 42,
     "lead_name": "Juan Pérez",
     "phone": "+56912345678",
     "message_text": "Hola? Alguien me va a responder?",
     "channel": "telegram",
     "assigned_to": 5
   }}
   ```

3. **Conversations Inbox** — filtrable por modo:
   ```python
   @router.get("")
   async def list_conversations(mode: Optional[str] = None):
       # mode="human" → solo leads en human_mode
       # mode="ai"    → solo leads manejados por IA
       # mode=None    → todos
       # Regla de visibilidad: leads en human_mode solo visibles
       # para el agente que los tomó
   ```

---

### 3.4 ¿Puede el Humano Devolver el Control a la IA?

**Sí.** Endpoint `POST /leads/{lead_id}/release`:

```python
@router.post("/leads/{lead_id}/release")
async def release_lead(lead_id, db, current_user):
    """Human agent releases control — AI resumes."""
    meta = dict(lead.lead_metadata or {})
    meta["human_mode"] = False
    meta.pop("human_assigned_to", None)
    meta.pop("human_taken_at", None)
    meta.pop("human_mode_notified", None)  # Reset para que el handoff message funcione de nuevo

    # IMPORTANTE: resetea el frustration score para que Sofía
    # reanude sin el estado de escalación anterior
    if "sentiment" in meta:
        from app.services.sentiment.scorer import empty_sentiment
        meta["sentiment"] = empty_sentiment()
        # → {"frustration_score": 0.0, "message_scores": [],
        #    "tone_hint": None, "escalated": False, "escalated_at": None}

    lead.lead_metadata = meta
    await db.commit()

    await ws_manager.broadcast(broker_id, "human_mode_changed", {
        "lead_id": lead_id,
        "human_mode": False,
    })
```

---

### 3.5 ¿Qué Pasa si el Humano No Responde a Tiempo?

**Actualmente NO hay timeout automático.** El lead queda en `human_mode=True` indefinidamente hasta que un humano haga `release`. Este es un **punto débil conocido** (ver sección 7).

---

### 3.6 ¿Se Mantiene el Historial Completo?

**Sí.** Todo el historial está en la tabla `chat_messages`:
- Mensajes del cliente: `direction="in"`, `ai_response_used=False`
- Mensajes de la IA: `direction="out"`, `ai_response_used=True`
- Mensajes del humano: `direction="out"`, `ai_response_used=False`

El humano ve TODO el historial (incluidas respuestas de la IA) al abrir la conversación en el inbox.

---

### 3.7 Flag de Control — Esquema Completo

El control vive en **`lead_metadata` (JSONB)** de la tabla `leads`:

```json
{
  "human_mode": true,              // ← FLAG PRINCIPAL: true = IA silenciada
  "human_assigned_to": 5,          // ID del usuario que tomó control
  "human_taken_at": "2026-04-02T15:30:00Z",
  "human_mode_notified": true,     // true = ya se envió el mensaje de handoff
  "sentiment": {
    "frustration_score": 0.82,     // 0.0-1.0, sliding window
    "message_scores": [            // últimos 3 mensajes
      {"score": 0.9, "emotions": ["abandonment_threat"], "ts": "..."},
      {"score": 0.7, "emotions": ["frustration"], "ts": "..."},
      {"score": 0.4, "emotions": ["confusion"], "ts": "..."}
    ],
    "tone_hint": null,             // "empathetic" | "calm" | null
    "escalated": true,             // se escaló automáticamente
    "escalated_at": "2026-04-02T15:28:00Z"
  }
}
```

**No hay una columna dedicada** — todo vive en el JSONB `metadata` del lead.

---

## 4. MODELO DE DATOS DE CONVERSACIONES

### 4.1 Esquema de `chat_messages`

```sql
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
    broker_id INTEGER REFERENCES brokers(id) ON DELETE CASCADE,

    -- Canal
    provider VARCHAR  -- 'telegram' | 'whatsapp' | 'instagram' | 'facebook' | 'tiktok' | 'webchat'
    channel_user_id VARCHAR(255),    -- ID del usuario en el canal
    channel_username VARCHAR(255),   -- Username visible
    channel_message_id VARCHAR(255), -- ID del mensaje en el provider

    -- Contenido
    message_text TEXT,
    direction VARCHAR,      -- 'in' (del cliente) | 'out' (del bot/humano)
    status VARCHAR,         -- 'pending' | 'sent' | 'delivered' | 'read' | 'failed'

    -- Metadatos
    provider_metadata JSONB,  -- datos específicos del canal (wamid, etc.)
    attachments JSONB,        -- [{type: "image", url: "..."}]

    -- Diferenciador IA vs Humano
    ai_response_used BOOLEAN DEFAULT TRUE,
    -- TRUE  = mensaje generado por la IA
    -- FALSE = mensaje del cliente (direction="in") O del humano (direction="out")

    prompt_version_id INTEGER REFERENCES prompt_versions(id),

    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);
```

### 4.2 Cómo Diferenciar Quién Envió

| `direction` | `ai_response_used` | Quién envió |
|---|---|---|
| `in` | `false` | **Cliente** |
| `out` | `true` | **IA (Sofía)** |
| `out` | `false` | **Humano (agente)** |

Cuando el humano envía un mensaje:
```python
# POST /leads/{lead_id}/human-message
msg = ChatMessage(
    lead_id=lead_id,
    broker_id=broker_id,
    provider=ChatProvider(provider_name),
    message_text=body.text,
    direction=MessageDirection.OUTBOUND,  # "out"
    status=MessageStatus.SENT,
    ai_response_used=False,               # ← marca como humano
    provider_metadata={"sent_by_human": True, "agent_id": user_id},
)
```

### 4.3 Estados de una Conversación

Las conversaciones **no tienen una tabla propia** — se derivan del estado del lead:

| Estado | Cómo se determina |
|---|---|
| **IA activa** | `lead_metadata.human_mode` es `False` o no existe |
| **Humano en control** | `lead_metadata.human_mode == True` |
| **Escalada por frustración** | `lead_metadata.sentiment.escalated == True` |
| **Conversation state** | `lead_metadata.conversation_state`: `GREETING`, `INTEREST_CHECK`, `DATA_COLLECTION`, `FINANCIAL_QUAL`, `SCHEDULING`, `COMPLETED` |
| **Pipeline stage** | `lead.pipeline_stage`: `entrada` → `perfilamiento` → `calificacion_financiera` → `potencial` → `agendado` → `ganado`/`perdido` |

---

## 5. CANALES DE COMUNICACIÓN

### 5.1 Canales Soportados

| Canal | Estado | Cómo llegan los mensajes |
|---|---|---|
| **Telegram** | ✅ Producción | Webhook → `POST /api/v1/telegram/webhook/{broker_id}` |
| **WhatsApp** | ✅ Producción | Webhook → `POST /api/v1/webhooks/whatsapp` (procesado via Celery task) |
| **Webchat** | ✅ Producción | HTTP POST → `POST /api/v1/chat/` |
| **Instagram** | 🔧 Enum definido | No implementado aún |
| **Facebook** | 🔧 Enum definido | No implementado aún |
| **TikTok** | 🔧 Enum definido | No implementado aún |
| **Voz (VAPI)** | ✅ Producción | Outbound calls via VAPI API |

### 5.2 Unificación en un Solo Flujo

**Todos los canales convergen en `ChatOrchestratorService.process_chat_message()`:**

```
Telegram webhook ──┐
WhatsApp webhook ──┤
Webchat HTTP POST ─┤──→ ChatOrchestratorService.process_chat_message()
Voice transcript ──┘       │
                           ├── Mismo pipeline de análisis
                           ├── Mismo multi-agent system
                           ├── Mismo scoring
                           └── Mismo pipeline stage advancement
```

Cada canal resuelve el `lead` por `(broker_id, provider, channel_user_id)`:
```python
# ChatService.find_lead_by_channel(db, broker_id, provider, channel_user_id)
# Busca en chat_messages el lead asociado a ese canal+user
```

Si no existe el lead, se crea automáticamente.

### 5.3 Comunicación en Tiempo Real

**WebSocket** — conexión persistente por `(broker_id, user_id)`:

```
Frontend → WS /ws/{broker_id}/{user_id}
         → Envía JWT como primer mensaje
         → Server valida token y broker
         → Mantiene conexión abierta
```

**Eventos del servidor:**
```typescript
type WSEvent =
  | { event: "connected",          data: { broker_id, user_id } }
  | { event: "new_message",        data: { lead_id, lead_name, message, provider } }
  | { event: "typing",             data: { lead_id, is_typing: boolean } }
  | { event: "ai_response",        data: { lead_id, message, new_score, status } }
  | { event: "stage_changed",      data: { lead_id, old_stage, new_stage } }
  | { event: "lead_assigned",      data: { lead_id, agent_id } }
  | { event: "lead_hot",           data: { lead_id, score } }
  | { event: "human_mode_changed", data: { lead_id, human_mode: boolean } }
  | { event: "human_mode_incoming",data: { lead_id, lead_name, message_text, channel } }
  | { event: "lead_frustrated",    data: { lead_id, frustration_score, emotions[] } }
  | { event: "ping",               data: {} }
```

**Fallback:** Si WebSocket no está disponible, el frontend debe hacer polling `GET /api/v1/leads` cada 30s.

**ConnectionManager (Singleton):**
```python
class ConnectionManager:
    _connections: Dict[int, List[tuple[str, WebSocket]]]  # broker_id → [(user_id, ws)]

    async def broadcast(broker_id, event, data) -> int:  # envía a TODOS del broker
    async def send_to_user(broker_id, user_id, event, data) -> bool:  # envía a UNO
    async def connect(broker_id, user_id, ws)
    async def disconnect(broker_id, user_id, ws)
```

---

## 6. FLUJOS PRINCIPALES

### 6.1 Lead Nuevo Escribe por Primera Vez

```
1. Cliente: "Hola, vi un departamento en Instagram y me interesa"
   → Llega por Telegram webhook

2. Telegram handler:
   → Resuelve broker_id por bot token
   → Busca lead por (broker_id, "telegram", chat_id) → NO EXISTE
   → Crea Lead(phone=str(chat_id), name="Telegram User",
              tags=["telegram"], pipeline_stage=NULL)

3. ChatOrchestratorService.process_chat_message():
   → Sanitiza input ✓
   → Log inbound message ✓
   → human_mode? → NO
   → WS: "new_message" + "typing"
   → ConversationStateMachine → state=GREETING
   → analyze_lead_qualification() → {interest_level: "high", score_delta: +15}
   → lead_score: 0 → 15
   → pipeline_stage: NULL → "entrada"
   → status: COLD

4. AgentSupervisor:
   → No current_agent → fallback to QualifierAgent
   → QualifierAgent.should_handle(stage="entrada") → YES
   → QualifierAgent.process():
     → System prompt: "Eres Sofía, asesora inmobiliaria..."
     → Missing fields: [nombre, teléfono, email, ubicación, renta, DICOM]
     → LLM responde: "¡Hola! 👋 Me llamo Sofía y soy asesora inmobiliaria.
       Me encanta que te haya llamado la atención. Para ayudarte mejor,
       ¿me podrías decir tu nombre?"
   → Return AgentResponse(message="¡Hola!...", agent_type=QUALIFIER)

5. Post-processing:
   → Log outbound message (ai_response_used=True)
   → WS: "typing"=false, "ai_response"
   → Celery: analyze_sentiment (background)
   → Envía respuesta por Telegram bot.send_message()
```

### 6.2 La IA Atiende y Agenda una Visita

```
[Varios turnos de QualifierAgent recopilando: nombre, teléfono, email,
 ubicación, renta, DICOM status]

1. Cliente: "Mi renta es 1.800.000 y no estoy en DICOM"

2. QualifierAgent.process():
   → analyze_lead_qualification() → {salary: 1800000, dicom_status: "clean"}
   → Merged context: is_appointment_ready() = TRUE, dicom_status != "dirty"
   → HandoffSignal(target=SCHEDULER, reason="All fields collected, DICOM clean")
   → Mensaje de transición: "¡Excelente, Juan! Con tu perfil financiero
     podemos avanzar. Te voy a ayudar a agendar una reunión con nuestro
     asesor financiero."

3. AgentSupervisor:
   → Aplica handoff → current_agent = SCHEDULER
   → pipeline_stage: perfilamiento → calificacion_financiera
   → Siguiente mensaje lo maneja SchedulerAgent

4. Cliente: "Dale, ¿cuándo puede ser?"

5. SchedulerAgent.process():
   → Carga tools: get_available_appointment_slots, create_appointment
   → LLM con function calling:
     → Llama get_available_appointment_slots(start="2026-04-03", end="2026-04-10")
     → Recibe: [{date: "2026-04-03", slots: ["10:00","11:00","15:00"]}, ...]
   → LLM responde: "Tengo estas opciones disponibles:
     📅 Jueves 3 de abril: 10:00, 11:00 o 15:00
     📅 Viernes 4 de abril: 09:00, 14:00
     ¿Cuál te acomoda más?"

6. Cliente: "El jueves a las 10 perfecto"

7. SchedulerAgent.process():
   → LLM llama create_appointment(
       lead_id=42,
       start_time="2026-04-03T10:00:00-03:00",
       appointment_type="virtual_meeting",
       notes="Reunión financiera"
     )
   → Crea Appointment + evento en Google Calendar
   → _is_appointment_confirmed("jueves a las 10 perfecto", response) → TRUE
   → HandoffSignal(target=FOLLOW_UP, reason="Appointment confirmed")
   → Responde: "✅ ¡Listo, Juan! Tu reunión queda confirmada para el
     jueves 3 de abril a las 10:00 hrs. Te llegará un link de Google Meet.
     Recuerda tener a mano tu cédula y las últimas 3 liquidaciones de sueldo."

8. pipeline_stage → "agendado"
   → WS: "stage_changed"
```

### 6.3 El Humano Toma Control en Medio de una Conversación

```
1. [Escenario A — Automático por frustración]

   Cliente: "CTM llevo 3 días esperando y nadie me llama, me voy a otra inmobiliaria"

   → Celery task: analyze_sentiment()
     → Heuristics: score=0.85 (anger + abandonment_threat)
     → Sliding window: accumulated=0.78
     → ActionLevel = ESCALATE (≥ 0.7)

   → escalation.py._escalate():
     → UPDATE leads SET metadata.human_mode = true,
                        metadata.sentiment.escalated = true
     → WS broadcast: "lead_frustrated" con emotions, score, last_message

   → Siguiente mensaje del cliente:
     → Orchestrator detecta human_mode=True
     → human_mode_notified=False → envía handoff message:
       "Entiendo tu frustración. Un agente se pondrá en contacto
        contigo muy pronto. 🙏"
     → human_mode_notified=True

   → Dashboard del agente: ve alerta roja con "lead_frustrated"
   → Abre conversación → ve TODO el historial (IA + cliente)

2. [Escenario B — Manual desde dashboard]

   → Agente hace click "Tomar control" en la UI
   → POST /leads/42/takeover
     → metadata.human_mode = True
     → metadata.human_assigned_to = 5
     → WS: "human_mode_changed"

   → Siguiente mensaje del cliente activaría el mismo flujo de arriba
```

### 6.4 El Humano Devuelve el Control a la IA

```
1. Agente humano resuelve el problema del cliente
2. Click "Devolver a Sofía" en la UI
3. POST /leads/42/release
   → metadata.human_mode = False
   → Borra: human_assigned_to, human_taken_at, human_mode_notified
   → Resetea sentiment: frustration_score=0, escalated=False, tone_hint=None
   → WS: "human_mode_changed" {human_mode: false}

4. Siguiente mensaje del cliente:
   → Orchestrator: human_mode? → NO
   → Procesamiento normal por IA
   → Sofía retoma desde donde quedó (tiene todo el contexto en BD)
   → El historial incluye los mensajes del humano (direction="out", ai_response_used=False)
```

---

## 7. DUDAS Y PUNTOS DÉBILES

### 7.1 Sin Timeout para Human Mode

**Problema:** Si un humano toma control y nunca responde (olvida, se va), el lead queda en `human_mode=True` para siempre. La IA no retoma.

**Impacto:** Leads perdidos silenciosamente. No hay Celery beat task que revise leads en human_mode sin respuesta.

**Solución propuesta:** Task periódica que revise `human_taken_at` > X horas sin mensajes outbound del humano → auto-release o notificación.

---

### 7.2 Handoff State en JSONB (No en Columna Tipada)

**Problema:** `human_mode`, `human_assigned_to`, etc. viven en `lead_metadata` (JSONB), no en columnas dedicadas con índices.

**Impacto:**
- No se puede hacer `WHERE human_mode = true` eficientemente (requiere JSON path query)
- No hay constraint de integridad (human_assigned_to no es FK real)
- Queries como "¿cuántos leads están en human mode?" requieren escaneo de JSONB

**Mitigación actual:** El volumen es bajo, pero escalará mal.

---

### 7.3 Sentiment Analysis es Asíncrona (Post-Respuesta)

**Problema:** El Celery task de sentiment analysis corre **después** de que la IA ya respondió. Si el cliente escribe algo muy agresivo, la IA responde primero y la escalación ocurre después.

**Impacto:** En el peor caso, la IA envía una respuesta genérica a un mensaje que claramente necesita intervención humana.

**Mitigación:** Las heurísticas de keywords podrían evaluarse **antes** del procesamiento IA (sync), y solo el LLM analyzer ser async.

---

### 7.4 No Hay Canal de Retorno para Webchat en Human Mode

**Problema:** Para Telegram y WhatsApp, el humano puede enviar mensajes al cliente vía `POST /leads/{id}/human-message` que usa el API del canal. Para **webchat**, no hay push real — el mensaje solo se loggea en BD.

**Impacto:** Si el lead llegó por webchat y está en human_mode, el humano no tiene forma de contactarlo (a menos que tenga su teléfono para escribirle por otro canal).

---

### 7.5 State Machine en Metadata (No en Tabla)

**Problema:** `conversation_state` y `current_agent` viven en JSONB, no hay auditoría de transiciones.

**Impacto:** Si algo corrompe el metadata, se pierde el estado de la conversación. No hay log de "pasó de QUALIFIER a SCHEDULER en timestamp X".

---

### 7.6 Single-Process WebSocket

**Problema:** `ws_manager` es un singleton in-memory. Si el backend corre en múltiples workers/pods, las conexiones WS se distribuyen entre procesos y `broadcast()` solo llega a las del proceso actual.

**Impacto:** En producción con múltiples workers, algunos dashboards no recibirán eventos en tiempo real.

**Solución:** Redis Pub/Sub o similar para coordinar broadcasts entre workers.

---

### 7.7 Sin CI/CD Automatizado

No hay `.github/workflows/` configurado. Los deploys son manuales o via Render auto-deploy desde branch.

---

### 7.8 DICOM Verification es Self-Reported

El estado DICOM del lead es lo que el propio lead declara ("No estoy en DICOM"). No hay integración real con Equifax/DICOM para verificación automatizada. Un lead podría mentir y avanzar a scheduling igualmente.

---

### 7.9 Concurrencia en Updates de Metadata

Múltiples procesos (orchestrator, sentiment task, pipeline service) hacen `jsonb_set` sobre el mismo `lead_metadata`. Aunque usan operaciones atómicas de PostgreSQL, no hay locking explícito — existe riesgo de race condition donde un update sobrescribe cambios del otro si operan sobre la misma sub-key.
