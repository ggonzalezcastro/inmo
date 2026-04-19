# Implementación Vapi — Referencia Técnica Completa

> Versión: post-auditoría 2026-03-01
> Basada en lectura directa del código. Documento canónico; reemplaza `VAPI_RESUMEN_EJECUTIVO.md` y `VAPI_CHECKLIST.md`.

---

## 1. Mapa de archivos

```
backend/app/
├── core/config.py                          # Variables de entorno Vapi (VAPI_API_KEY, etc.)
├── main.py                                 # validate_config() en lifespan startup
│
├── models/
│   ├── voice_call.py                       # VoiceCall, CallTranscript, CallStatus, SpeakerType
│   └── broker_voice_config.py              # BrokerVoiceConfig (config por broker)
│
├── routes/
│   └── voice.py                            # Endpoints REST + _handle_vapi_webhook()
│
├── features/voice/routes.py                # Re-export del router anterior
│
├── services/voice/
│   ├── __init__.py
│   ├── call_service.py                     # VoiceCallService (lógica principal)
│   ├── call_agent.py                       # CallAgentService (LLM: resumen post-llamada)
│   ├── base_provider.py                    # Interfaz abstracta BaseVoiceProvider
│   ├── factory.py                          # get_voice_provider() — registro de providers
│   ├── provider.py                         # _VapiProviderCompat (compat shim, no tocar)
│   ├── types.py                            # WebhookEvent, CallEventType, MakeCallRequest, …
│   └── providers/vapi/
│       ├── __init__.py
│       ├── provider.py                     # VapiProvider (implementación real)
│       └── assistant_service.py            # VapiAssistantService (CRUD assistants en Vapi)
│
├── services/broker/
│   └── voice_config_service.py             # BrokerVoiceConfigService (config + build_assistant_config)
│
├── tasks/
│   ├── base.py                             # DLQTask base class
│   └── voice_tasks.py                      # process_end_of_call_report (DLQTask)
│                                           # generate_call_transcript_and_summary (DEPRECATED)
└── schemas/
    └── voice_call.py                       # VoiceCallResponse, CallInitiateRequest
```

---

## 2. Arquitectura general

```
                ┌──────────────────────┐
                │    Frontend / API    │
                └──────────┬───────────┘
                           │ POST /api/v1/calls/initiate (JWT)
                           ▼
              ┌────────────────────────────┐
              │   routes/voice.py          │
              │   VoiceCallService         │
              │   .initiate_call()         │
              └──────┬─────────────────────┘
                     │
         ┌───────────┼────────────────────────────┐
         │           │                            │
         ▼           ▼                            ▼
  _resolve_     _company_broker          BrokerVoiceConfigService
  broker_       _id_for_user()           .get_phone_number_id()
  user_id()     └─ ValueError si None   .get_assistant_id()
                  (C4)                   └─ Redis → DB → env var
         │
         ▼
  VapiProvider.make_call()
         │
         ▼
  POST https://api.vapi.ai/call
         │
         └─► external_call_id → VoiceCall.external_call_id


                ┌──────────────────────┐
                │   Vapi (webhooks)    │
                └──────────┬───────────┘
                           │ POST /api/v1/calls/webhooks/voice
                           │   header: x-vapi-secret: ...
                           ▼
              ┌────────────────────────────┐
              │  _handle_vapi_webhook()    │
              │  1. Verifica x-vapi-secret │  (C1)
              │  2. provider.handle_webhook│  → WebhookEvent
              │  3. Dispatch por event_type│
              └──────┬─────────────────────┘
                     │
        ┌────────────┼──────────────┬──────────────────┐
        ▼            ▼              ▼                   ▼
  TOOL_CALLS   ASSISTANT_      END_OF_CALL_        STATUS /
  handle_tool  REQUEST         REPORT              TRANSCRIPT
  _call()      DB lookup       Celery task         handle_normalized
  dispatcher   phone→assistant process_end_        _event()
  (A1)         _id             of_call_report      → VoiceCall DB
```

---

## 3. Flujo de llamada saliente (paso a paso)

### 3.1 Entrada

```
POST /api/v1/calls/initiate
Authorization: Bearer <jwt>

{
  "lead_id": 42,
  "campaign_id": null,      // opcional
  "agent_type": "perfilador" // opcional, default "default"
}
```

### 3.2 `VoiceCallService.initiate_call()` — `call_service.py`

1. Busca `Lead` por `lead_id` → error 404 si no existe
2. Verifica `lead.phone` → error 400 si vacío
3. `_resolve_broker_user_id()` — resuelve user ID del agente:
   - Si `broker_id` pasado → usa ese
   - Else → `lead.assigned_to`
   - Else → `campaign.broker_id` si hay campaña
   - Else → `ValueError`
4. `_company_broker_id_for_user()` — resuelve company broker ID (FK a `brokers.id`)
   - **Guard C4:** si `company_broker_id is None` → `ValueError` descriptivo
5. Crea `VoiceCall` en DB con `status=INITIATED`
6. Llama `VapiProvider.make_call()`

### 3.3 `VapiProvider.make_call()` — `providers/vapi/provider.py`

1. Verifica `VAPI_API_KEY`
2. `BrokerVoiceConfigService.get_phone_number_id(db, company_broker_id)`:
   - Redis cache (TTL 1h) → DB `broker_voice_configs.phone_number_id` → `settings.VAPI_PHONE_NUMBER_ID`
3. `BrokerVoiceConfigService.get_assistant_id(db, company_broker_id, agent_type)`:
   - `assistant_id_by_type[agent_type]` → `assistant_id_default` → `settings.VAPI_ASSISTANT_ID`
4. Construye `webhook_url = settings.WEBHOOK_BASE_URL + "/api/v1/calls/webhooks/voice"`
5. `POST https://api.vapi.ai/call` con payload:
   ```json
   {
     "assistantId": "asst_...",
     "phoneNumberId": "phn_...",
     "customer": { "number": "+56912345678", "numberE164CheckEnabled": true },
     "assistantOverrides": { "server": { "url": "<webhook_url>" } },
     "metadata": { "lead_id": 42, "campaign_id": null, "broker_id": 1, "assistant_type": "perfilador" }
   }
   ```
   > `assistantOverrides.server.url` tiene máxima prioridad sobre el server URL configurado en el dashboard — permite un solo assistant con múltiples brokers.
6. Devuelve `call_id` (el ID de Vapi) → se guarda en `VoiceCall.external_call_id`

---

## 4. Flujo de webhooks entrantes

### 4.1 Seguridad (C1)

```python
# Antes de cualquier procesamiento en _handle_vapi_webhook():
if settings.VAPI_WEBHOOK_SECRET:
    token = headers.get("x-vapi-secret") or ""
    if token != settings.VAPI_WEBHOOK_SECRET:
        return {"error": "Unauthorized"}   # HTTP 200, body de error
```

Configurar en Vapi dashboard → Assistant → Server URL → Secret.

### 4.2 Parsing — `VapiProvider.handle_webhook()`

Normaliza el payload a `WebhookEvent` con campos:

| Campo | Descripción |
|---|---|
| `event_type` | `CallEventType` enum |
| `external_call_id` | `message.call.id` |
| `status` | estado de Vapi |
| `transcript` | texto del transcript |
| `artifact_messages` | lista estructurada de mensajes |
| `tool_calls_data` | lista de tool calls |
| `ended_reason` | motivo de finalización |
| `recording_url` | URL de la grabación |
| `broker_id` | de `call.metadata.broker_id` |
| `assistant_type` | de `call.metadata.assistant_type` |

### 4.3 Dispatch por tipo de evento

| `message.type` de Vapi | `CallEventType` | Acción |
|---|---|---|
| `status-update` | STATUS_UPDATE / CALL_RINGING / CALL_ANSWERED / CALL_ENDED / CALL_FAILED | Actualiza `VoiceCall.status` en DB |
| `call-started` | CALL_STARTED | Actualiza status |
| `transcript` | TRANSCRIPT_UPDATE | Log sin persistir (transcript completo llega en `end-of-call-report`) |
| `tool-calls` | TOOL_CALLS | `handle_tool_call()` → respuesta a Vapi |
| `end-of-call-report` | END_OF_CALL_REPORT | Celery: `process_end_of_call_report.delay()` |
| `assistant-request` | ASSISTANT_REQUEST | DB lookup por `phone_number_id` → devuelve `assistantId` |
| `hang` | HANG | Solo log |

> Todos los webhooks devuelven **HTTP 200**. Vapi reintenta si recibe otro código.

### 4.4 Tool calls (A1)

Respuesta esperada por Vapi:
```json
{
  "results": [
    { "toolCallId": "tc_xxx", "name": "schedule_appointment", "result": "Entendido, un asesor te contactará..." }
  ]
}
```

Dispatcher en `call_service.handle_tool_call()`:

| Tool name | Comportamiento |
|---|---|
| `schedule_appointment` | Log con `lead_id` + mensaje de confirmación al lead |
| `update_lead_stage` | Log + confirmación |
| Desconocido | Warning en logs + `"Acción registrada."` |

> La integración real con `AppointmentService` es trabajo pendiente.

### 4.5 ASSISTANT_REQUEST

Cuando Vapi no tiene assistant pre-asignado, envía este evento. El backend busca por `phone_number_id`:

```python
SELECT assistant_id_default FROM broker_voice_configs
WHERE phone_number_id = '<phn_xxx>'
```

Si existe → `{"assistantId": "asst_xxx"}`. Si no → `{"error": "No assistant configured"}`.

---

## 5. Post-call pipeline (end-of-call-report)

```
Vapi envía end-of-call-report
  │
  ▼
process_end_of_call_report.delay(
    external_call_id, transcript, artifact_messages, ended_reason, recording_url
)
```

Task: `tasks/voice_tasks.py` — `DLQTask`, `max_retries=3`, backoff 60s/120s/180s.

**Dentro del task:**

```
1. SELECT VoiceCall WHERE external_call_id = ?
2. VoiceCallService.update_call_transcript(transcript)        → VoiceCall.transcript
3. VoiceCallService.store_transcript_lines(                   → tabla call_transcripts
       artifact_messages,                                       (fuente primaria)
       transcript_text                                          (fallback: texto plano)
   )
4. Actualiza VoiceCall.recording_url si hay recording_url
5. SELECT Lead WHERE id = voice_call.lead_id
6. CallAgentService.generate_call_summary(transcript, lead_context)
   └─ LLM genera JSON:
      { summary, interest_level, budget, timeline, score_delta, stage_to_move }
   └─ Parser: json.loads() directo → regex de fallback si falla
7. VoiceCallService.update_call_summary(summary, score_delta, stage_after_call)
8. Actualiza lead.lead_metadata[budget, timeline]
9. Actualiza lead.lead_score += score_delta
10. PipelineService.move_lead_to_stage(stage_to_move)  (si hay)
11. db.commit()
```

**Si falla:** retry con backoff exponencial. Tras 3 intentos → DLQ (visible en `GET /api/v1/admin/dlq`).

---

## 6. Almacenamiento de transcript (M4)

`VoiceCallService.store_transcript_lines()`:

**Fuente primaria — `artifact_messages`** (estructura de Vapi):
```json
[
  { "role": "assistant", "message": "Hola, ¿cómo estás?", "secondsFromStart": 0.0 },
  { "role": "user",      "message": "Hola, bien gracias.", "secondsFromStart": 3.2 },
  { "role": "tool",      "message": "...",                 "secondsFromStart": 5.0 }
]
```
- `role=assistant` → `SpeakerType.BOT`
- `role=user` → `SpeakerType.CUSTOMER`
- `role=tool/system/tool_call` → omitido

**Fallback — string plano** (si `artifact_messages` está vacío):
```
Bot: Hola, ¿cómo estás?
User: Hola, bien gracias.
```
Timestamps se asignan secuencialmente (+1s por línea, sin info real de tiempo).

Modelo `CallTranscript`:
| Campo | Tipo | Descripción |
|---|---|---|
| `voice_call_id` | FK | Referencia a `voice_calls.id` |
| `speaker` | Enum | `bot` o `customer` |
| `text` | Text | Contenido del mensaje |
| `timestamp` | Float | Segundos desde inicio de llamada |
| `confidence` | Float? | Score STT (null para Vapi transcript) |

---

## 7. Configuración por broker

### 7.1 `BrokerVoiceConfig` (DB)

Tabla `broker_voice_configs` — un registro por broker.

| Campo | Tipo | Default | Descripción |
|---|---|---|---|
| `broker_id` | FK brokers | — | Unique por broker |
| `provider` | String | `"vapi"` | Provider activo |
| `phone_number_id` | String | null | Phone Number ID de Vapi |
| `assistant_id_default` | String | null | Assistant por defecto |
| `assistant_id_by_type` | JSONB | `{}` | `{"perfilador": "asst_aaa"}` |
| `voice_config` | JSONB | ver defaults | `{"provider": "azure", "voiceId": "es-MX-DaliaNeural"}` |
| `model_config` | JSONB | ver defaults | `{"provider": "openai", "model": "gpt-4o", "temperature": 0.7}` |
| `transcriber_config` | JSONB | ver defaults | `{"provider": "deepgram", "model": "nova-2", "language": "es"}` |
| `timing_config` | JSONB | ver defaults | `{"maxDurationSeconds": 300, "waitSeconds": 0.4, ...}` |
| `end_call_config` | JSONB | ver defaults | frases de cierre y mensaje final |
| `first_message_template` | Text | null | Saludo inicial con `{broker_name}`, `{broker_company}` |
| `recording_enabled` | Boolean | `true` | |

### 7.2 Defaults (`voice_config_service.py`)

```python
DEFAULT_VOICE_CONFIG       = {"provider": "azure", "voiceId": "es-MX-DaliaNeural"}
DEFAULT_MODEL_CONFIG       = {"provider": "openai", "model": "gpt-4o", "temperature": 0.7}
DEFAULT_TRANSCRIBER_CONFIG = {"provider": "deepgram", "model": "nova-2", "language": "es"}
DEFAULT_TIMING_CONFIG      = {"maxDurationSeconds": 300, "waitSeconds": 0.4,
                               "voiceSeconds": 0.3, "backoffSeconds": 1.2}
DEFAULT_END_CALL_CONFIG    = {"endCallMessage": "Muchas gracias...",
                               "endCallPhrases": ["adiós", "chao", "no me interesa", ...]}
```

### 7.3 Cache Redis

`BrokerVoiceConfigService.get_voice_config()` cachea en Redis con key `broker_voice:{broker_id}`, TTL 1 hora. Invalidar manualmente si se cambia la config:

```bash
redis-cli DEL "broker_voice:1"
```

### 7.4 Resolución encadenada de `assistant_id`

```
BrokerVoiceConfigService.get_assistant_id(db, broker_id, agent_type)
  1. broker_voice_configs.assistant_id_by_type[agent_type]
  2. broker_voice_configs.assistant_id_default
  3. settings.VAPI_ASSISTANT_ID
  4. ValueError (la llamada falla con 500)
```

---

## 8. Gestión de assistants

### 8.1 Crear desde config del broker (recomendado)

```
POST /api/v1/brokers/config/voice/assistant
Authorization: Bearer <jwt_admin>
```

Internamente:
1. `BrokerVoiceConfigService.build_assistant_config(db, broker_id)`:
   - Obtiene prompt del chat (`BrokerConfigService.build_system_prompt()`)
   - `adapt_prompt_for_voice()` — elimina sección de herramientas, agrega instrucciones de voz
   - Construye JSON completo de assistant con voice, model, transcriber, timing
2. `VapiAssistantService.create_assistant_for_broker()` → `POST https://api.vapi.ai/assistant`
3. Devuelve el objeto assistant completo (incluyendo `id`)

Guardar el `id` devuelto en `broker_voice_configs.assistant_id_default`.

### 8.2 `adapt_prompt_for_voice()`

Transforma el prompt de chat:
- Añade header de instrucciones para voz (máx 2-3 oraciones, una pregunta a la vez)
- Elimina la sección `## HERRAMIENTAS DISPONIBLES` (no aplica en Vapi)
- Reemplaza referencias a "mensaje"/"chat" por referencias de voz
- Ajusta instrucciones de formato

### 8.3 CRUD de assistants (`VapiAssistantService`)

| Método | API Vapi |
|---|---|
| `create_assistant_for_broker(db, broker_id)` | `POST /assistant` |
| `get_assistant(assistant_id)` | `GET /assistant/{id}` |
| `list_assistants()` | `GET /assistant` |
| `update_assistant(assistant_id, updates)` | `PATCH /assistant/{id}` |
| `delete_assistant(assistant_id)` | `DELETE /assistant/{id}` |

---

## 9. Integración con campañas (C2)

Un step de campaña con `action: "make_call"` ejecuta `_execute_make_call()`:

```python
# tasks/campaign_executor.py
voice_call = await VoiceCallService.initiate_call(
    db=db,
    lead_id=lead.id,
    campaign_id=campaign.id,
    broker_id=campaign.broker_id,   # user ID del dueño de la campaña
    agent_type=step.config.get("agent_type") or "default",
)
log.status = COMPLETED
log.response = {
    "voice_call_id": voice_call.id,
    "external_call_id": voice_call.external_call_id,
    "status": voice_call.status.value
}
```

Config de un step en DB (`campaign_steps.config`):
```json
{ "agent_type": "perfilador" }
```

`ValueError` (lead sin teléfono, assistant no configurado) → log `FAILED` con mensaje descriptivo; no propaga excepción.

---

## 10. Variables de entorno

```bash
# --- OBLIGATORIAS ---
VAPI_API_KEY=sk-...                          # API key global (Bearer token)
WEBHOOK_BASE_URL=https://api.tudominio.com   # URL pública del backend (sin trailing slash)
VOICE_PROVIDER=vapi                          # Activa VapiProvider como default

# --- OBLIGATORIAS EN PRODUCCIÓN ---
VAPI_WEBHOOK_SECRET=secreto-largo-aleatorio  # x-vapi-secret header — sin esto cualquiera puede enviar webhooks

# --- FALLBACK GLOBAL (si broker no tiene config en DB) ---
VAPI_PHONE_NUMBER_ID=phn_...                # Phone Number ID de Vapi
VAPI_ASSISTANT_ID=asst_...                  # Assistant ID de Vapi
```

> Si `VAPI_WEBHOOK_SECRET` está vacío, la verificación se salta (modo dev). En producción DEBE configurarse.

---

## 11. Endpoints de la API

| Método | Path | Auth | Descripción |
|---|---|---|---|
| `POST` | `/api/v1/calls/initiate` | JWT | Inicia llamada saliente a un lead |
| `POST` | `/api/v1/calls/webhooks/voice` | `x-vapi-secret` | Webhook de Vapi (provider default) |
| `POST` | `/api/v1/calls/webhooks/voice/{provider}` | `x-vapi-secret` | Webhook por provider explícito |
| `GET` | `/api/v1/calls/leads/{lead_id}` | JWT | Historial de llamadas de un lead |
| `GET` | `/api/v1/calls/{call_id}` | JWT | Detalle + `transcript_lines` de una llamada |
| `POST` | `/api/v1/brokers/config/voice/assistant` | JWT admin | Crea assistant en Vapi desde config del broker |

---

## 12. Modelo `voice_calls`

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | Integer PK | |
| `lead_id` | FK leads | Lead que recibió la llamada |
| `campaign_id` | FK campaigns | Nullable — campaña que originó la llamada |
| `phone_number` | String | Número marcado |
| `external_call_id` | String unique | ID de Vapi (indexed) |
| `status` | Enum | `initiated → ringing → answered → completed / failed / no_answer / busy / cancelled` |
| `duration` | Integer | Segundos (nullable) |
| `recording_url` | String | URL de la grabación en Vapi |
| `transcript` | Text | Transcript completo (string plano de Vapi) |
| `summary` | Text | Resumen generado por LLM |
| `stage_after_call` | String | Stage recomendado por el LLM |
| `score_delta` | Float | Cambio de score aplicado al lead |
| `started_at` | DateTime | |
| `completed_at` | DateTime | |
| `broker_id` | FK users | User ID del agente (≠ company broker ID) |

Tabla relacionada `call_transcripts`:
| Campo | Tipo | Descripción |
|---|---|---|
| `voice_call_id` | FK | |
| `speaker` | Enum | `bot` / `customer` |
| `text` | Text | |
| `timestamp` | Float | Segundos desde inicio |
| `confidence` | Float? | Siempre null con Vapi (viene del artifact, sin score) |

---

## 13. Validación de credenciales en startup

`VapiProvider.validate_config()` hace `GET https://api.vapi.ai/call?limit=1` con timeout 5s:
- 200 → API key válida, log `INFO`
- 401 → API key inválida, log `ERROR`
- Error de red → log `WARNING`, no bloquea startup

Se llama en `main.py` lifespan si `VAPI_API_KEY` está configurado. La app arranca igual aunque falle.

---

## 14. Celery — requisitos

**Pool requerido: `prefork` (default de Celery)**

Las tasks de voz usan `asyncio.run()` dentro de funciones síncronas de Celery. Incompatible con `--pool=gevent` o `--pool=eventlet`.

```bash
# Correcto
celery -A app.celery_app worker --pool=prefork --loglevel=info

# Incorrecto (rompe las tasks de voz)
celery -A app.celery_app worker --pool=gevent
```

Task `process_end_of_call_report`:
- Base: `DLQTask` (auto-push a DLQ tras agotar retries)
- `max_retries=3`
- Backoff: 60s → 120s → 180s
- DLQ visible en `GET /api/v1/admin/dlq`

---

## 15. Setup inicial (guía operativa)

### Paso 1 — Configurar env vars

```bash
# .env
VAPI_API_KEY=sk-...
WEBHOOK_BASE_URL=https://api.tudominio.com
VAPI_WEBHOOK_SECRET=$(openssl rand -hex 32)
VOICE_PROVIDER=vapi
```

### Paso 2 — Crear BrokerVoiceConfig en DB

```sql
INSERT INTO broker_voice_configs (broker_id, provider, recording_enabled)
VALUES (1, 'vapi', true);
```

O via API (próximamente).

### Paso 3 — Crear assistant en Vapi desde la config del broker

```bash
curl -X POST https://api.tudominio.com/api/v1/brokers/config/voice/assistant \
  -H "Authorization: Bearer $JWT_ADMIN"
```

Guardar el `id` devuelto:
```sql
UPDATE broker_voice_configs
SET assistant_id_default = 'asst_xxx'
WHERE broker_id = 1;
```

### Paso 4 — Comprar/importar phone number en Vapi dashboard

Guardar el `Phone Number ID`:
```sql
UPDATE broker_voice_configs
SET phone_number_id = 'phn_xxx'
WHERE broker_id = 1;
```

### Paso 5 — Configurar el Secret en Vapi dashboard

En Vapi dashboard → el assistant → Server URL → Secret: pegar el valor de `VAPI_WEBHOOK_SECRET`.

### Paso 6 — Invalidar cache Redis

```bash
redis-cli DEL "broker_voice:1"
```

### Paso 7 — Verificar al arrancar el backend

Al startup aparece en logs:
```
INFO  Vapi API key validated successfully
```
Si aparece `WARNING Vapi API key validation failed`, revisar `VAPI_API_KEY`.

---

## 16. Troubleshooting

### Llamada no inicia → `ValueError: No phone_number_id configured`
Falta `BrokerVoiceConfig.phone_number_id` y `VAPI_PHONE_NUMBER_ID` env var.

### Llamada no inicia → `ValueError: No assistant_id configured`
Falta `BrokerVoiceConfig.assistant_id_default` (o `_by_type`) y `VAPI_ASSISTANT_ID` env var.

### Llamada no inicia → `ValueError: User X has no broker (company) assigned`
El user que hace la llamada no tiene `broker_id` en su registro de `users`. Asignar el broker en la DB.

### Webhook devuelve `{"error": "Unauthorized"}`
El header `x-vapi-secret` no coincide con `VAPI_WEBHOOK_SECRET`. Verificar la config en Vapi dashboard → Secret.

### `transcript_lines` siempre vacío
`artifact_messages` llegó vacío Y el transcript no tiene el formato `"Bot: ...\nUser: ..."`. Revisar la respuesta raw del webhook en logs.

### `process_end_of_call_report` no procesa
1. Verificar que Celery worker está corriendo con prefork
2. Revisar DLQ: `GET /api/v1/admin/dlq` — si el task está ahí, ver el error
3. Verificar logs del worker: `celery -A app.celery_app worker --loglevel=debug`

### Config de broker no se actualiza después de cambiar en DB
El cache Redis TTL es 1 hora. Invalidar manualmente: `redis-cli DEL "broker_voice:{broker_id}"`

### `asyncio.run()` falla con `RuntimeError: This event loop is already running`
El worker está usando gevent/eventlet. Cambiar a prefork: `celery ... worker --pool=prefork`.

---

## 17. Pendientes (baja prioridad)

| ID | Descripción | Complejidad |
|---|---|---|
| B2 | Renombrar `VoiceCall.broker_id` → `agent_user_id` en código y DB | Alta — requiere migración |
| M5 | `provider_credentials` por broker (API key multi-tenant) | Media — requiere encriptación |
| WS | `ws_manager.broadcast()` al frontend en eventos de llamada | Media |
| Tool | Integración real de `schedule_appointment` con `AppointmentService` | Media |
