# API Endpoints

Base URL: `http://localhost:8000`  
All endpoints except `/auth/register`, `/auth/login`, `GET /webhooks/*`, and `GET /health` require:
```
Authorization: Bearer <access_token>
```

---

## Auth — `/auth`

### `POST /auth/register`
Registers a new broker account. Creates `User` (role=ADMIN), `Broker`, and all default configs.

**Body:**
```json
{
  "email": "admin@inmobiliaria-activa.cl",
  "password": "Seguro123!",
  "broker_name": "Inmobiliaria Activa"
}
```
**Password rules:** min 8 chars, at least 1 digit and 1 special character.

**Response `200`:**
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```
**Errors:** `400` email already registered · `422` weak password / invalid email

---

### `POST /auth/login`
Authenticate and receive a JWT Bearer token.

**Body:**
```json
{ "email": "admin@inmobiliaria-activa.cl", "password": "Seguro123!" }
```
**Response `200`:** same as `/register`  
**Error:** `401` invalid credentials

---

### `GET /auth/me`
Returns the authenticated user's profile.

**Response `200`:**
```json
{
  "id": 1,
  "email": "admin@inmobiliaria-activa.cl",
  "name": "Inmobiliaria Activa",
  "role": "ADMIN",
  "broker_id": 1,
  "is_active": true
}
```

---

## Leads — `/api/v1/leads`

### `GET /api/v1/leads`
List leads. Results filtered by role: AGENT sees only their assigned leads; ADMIN sees broker leads; SUPERADMIN sees all.

**Query params:**
| Param | Type | Default | Description |
|---|---|---|---|
| status | string | | Filter: `cold`\|`warm`\|`hot`\|`converted`\|`lost` |
| min_score | float | 0 | |
| max_score | float | 100 | |
| search | string | | Matches name, phone, or email |
| pipeline_stage | string | | Filter by pipeline stage |
| skip | int | 0 | |
| limit | int | 50 | max 200 |

**Response `200`:**
```json
{
  "data": [{"id": 1, "phone": "+56912345678", "name": "María", "status": "warm", "lead_score": 42.5, ...}],
  "total": 1,
  "skip": 0,
  "limit": 50
}
```

---

### `GET /api/v1/leads/{lead_id}`
Get full lead detail including last 10 activity log entries.

**Response `200`:** `LeadDetailResponse` with `recent_activities[]`  
**Error:** `404` lead not found

---

### `POST /api/v1/leads`
Create a new lead manually.

**Body:**
```json
{ "phone": "+56912345678", "name": "María", "email": "maria@email.com", "tags": ["activo"] }
```
**Response `201`:** `LeadResponse`

---

### `PUT /api/v1/leads/{lead_id}`
Update lead fields. Partial update supported.

---

### `DELETE /api/v1/leads/{lead_id}`
Delete lead and all related records (cascade). **Response `204`**

---

### `PUT /api/v1/leads/{lead_id}/assign`
Assign lead to an agent. **ADMIN only.** Agent must belong to the same broker.

**Body:** `{ "agent_id": 3 }`

---

### `PUT /api/v1/leads/{lead_id}/pipeline`
Manually move lead to a pipeline stage.

**Body:** `{ "stage": "agendado" }`

**Valid stages:** `entrada` · `perfilamiento` · `calificacion_financiera` · `agendado` · `seguimiento` · `referidos` · `ganado` · `perdido`

---

### `POST /api/v1/leads/{lead_id}/recalculate`
Force recalculate lead score, qualification, and pipeline stage.

**Response `200`:**
```json
{ "lead_id": 1, "score": 68.5, "calificacion": "potencial", "pipeline_stage": "calificacion_financiera" }
```

---

### `POST /api/v1/leads/bulk-import`
Bulk import from CSV. Accepts `multipart/form-data` with field `file` (.csv only).  
CSV columns: `phone`, `name`, `email`, `tags` (comma-separated).

**Response `200`:**
```json
{ "imported": 45, "duplicates": 3, "invalid": 1 }
```

---

## Chat — `/api/v1/chat`

### `POST /api/v1/chat/test`
Send a message to Sofía and receive a full AI response.

**Body:**
```json
{
  "message": "Hola, me interesa un departamento de 2 dormitorios en Las Condes",
  "lead_id": null,
  "provider": "webchat"
}
```
- `lead_id`: optional. If omitted, a new lead is created.
- `message`: max 4000 chars, XSS-sanitized.

**Response `200`:**
```json
{
  "response": "¡Hola! Soy Sofía. ¿Cuál es tu nombre?",
  "lead_id": 42,
  "lead_score": 15.0,
  "lead_status": "cold"
}
```
**Errors:** `404` lead_id not found · `422` message empty/too long

---

### `POST /api/v1/chat/stream`
Same as `/test` but streams tokens via **SSE (Server-Sent Events)**.

**Response:** `text/event-stream`

Each event:
```
data: {"token": "Hola"}

data: {"token": ", soy"}

data: {"done": true, "lead_id": 42, "lead_score": 15.0, "lead_status": "cold", "conversation_state": "greeting"}
```

On error:
```
data: {"error": "...", "code": "validation_error"}
```

Fallback: if provider doesn't support `stream_generate`, the pre-computed response is split word-by-word with ~15ms delay.

Headers set: `Cache-Control: no-cache`, `X-Accel-Buffering: no` (disables Nginx buffering).

---

### `GET /api/v1/chat/{lead_id}/messages`
Get chat history for a lead. Prefers `chat_messages` table; falls back to `telegram_messages`.

**Query params:** `skip`, `limit` (default 100), `provider` (optional filter)

**Response `200`:**
```json
{
  "lead_id": 42,
  "provider": "chat_messages",
  "messages": [
    { "id": 1, "direction": "in", "message_text": "Hola", "sender_type": "customer", "created_at": "...", "ai_response_used": false, "provider": "webchat" }
  ],
  "total": 1, "skip": 0, "limit": 100
}
```

---

### `GET /api/v1/chat/verify/{lead_id}`
Debug endpoint: returns lead data, all messages, activity logs, and data completeness summary (`has_name`, `has_phone`, `has_location`, `has_budget`).

---

## Appointments — `/api/v1/appointments`

Full CRUD for appointments. Integrates with Google Calendar when `GOOGLE_CLIENT_ID` is configured.

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/appointments` | List appointments (filters: `lead_id`, `agent_id`, `status`, `date_from`, `date_to`) |
| POST | `/api/v1/appointments` | Create appointment |
| GET | `/api/v1/appointments/{id}` | Get appointment detail |
| PUT | `/api/v1/appointments/{id}` | Update appointment |
| DELETE | `/api/v1/appointments/{id}` | Cancel/delete appointment |
| GET | `/api/v1/appointments/available-slots` | Get available time slots |

---

## Campaigns — `/api/v1/campaigns`

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/campaigns` | List campaigns |
| POST | `/api/v1/campaigns` | Create campaign |
| GET | `/api/v1/campaigns/{id}` | Get campaign detail |
| PUT | `/api/v1/campaigns/{id}` | Update campaign |
| DELETE | `/api/v1/campaigns/{id}` | Delete campaign |
| POST | `/api/v1/campaigns/{id}/steps` | Add step to campaign |
| POST | `/api/v1/campaigns/{id}/apply` | Apply campaign to leads |
| GET | `/api/v1/campaigns/{id}/logs` | Get execution logs |

---

## Pipeline — `/api/v1/pipeline`

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/pipeline` | Pipeline board: leads grouped by stage |
| GET | `/api/v1/pipeline/metrics` | Funnel KPIs and conversion rates |
| POST | `/api/v1/pipeline/auto-advance` | Trigger auto-advance check (admin) |

---

## Templates — `/api/v1/templates`

CRUD for message templates. Supports variable interpolation: `{{name}}`, `{{broker_name}}`, `{{date}}`, etc.

---

## Voice — `/api/v1/calls`

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/calls` | Initiate outbound AI voice call via VAPI |
| GET | `/api/v1/calls` | List calls for broker |
| GET | `/api/v1/calls/{id}` | Get call detail + transcript |
| POST | `/api/v1/calls/webhook` | VAPI webhook receiver (call status, transcript) |

---

## Webhooks — `/webhooks`

| Method | Path | Description |
|---|---|---|
| POST | `/webhooks/telegram` | Telegram bot webhook (called by Telegram) |
| GET | `/webhooks/whatsapp` | WhatsApp webhook verification |
| POST | `/webhooks/whatsapp` | WhatsApp message receiver |

---

## Knowledge Base — `/api/v1/kb`

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/kb` | List KB entries for broker |
| POST | `/api/v1/kb` | Create entry (auto-embeds with Gemini text-embedding-004) |
| GET | `/api/v1/kb/{id}` | Get entry |
| PUT | `/api/v1/kb/{id}` | Update entry (re-embeds) |
| DELETE | `/api/v1/kb/{id}` | Delete entry |
| POST | `/api/v1/kb/search` | Semantic search (cosine similarity via pgvector) |

---

## Broker Config — `/api/broker`

ADMIN/SUPERADMIN only. Manage AI agent identity, prompt sections, lead scoring weights, and prompt version history.

---

## Broker Users — `/api/broker`

ADMIN/SUPERADMIN only. Create, update, deactivate users within a broker.

---

## Brokers — `/api/brokers`

SUPERADMIN only. Full broker CRUD.

---

## Costs — `/api/v1/admin/costs`

LLM cost analytics: per-broker summary, daily chart data, outlier detection, CSV export, cross-broker aggregation (SUPERADMIN).

---

## Admin Tasks — `/api/v1/admin/tasks`

DLQ (Dead Letter Queue) management for failed Celery tasks: list, retry, discard.

---

## WebSocket — `/ws/{broker_id}/{user_id}`

Real-time event stream. See [architecture/overview.md](../architecture/overview.md#5-real-time-updates) for full protocol.

---

## Utility

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | No | API info + docs link |
| GET | `/health` | No | DB, Redis, circuit breakers, cache stats |
| GET | `/docs` | No | Swagger UI |
| GET | `/redoc` | No | ReDoc UI |
