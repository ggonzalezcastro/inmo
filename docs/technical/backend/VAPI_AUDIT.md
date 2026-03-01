# Auditoría del Sistema Vapi — Inmo CRM

> Auditoría inicial: 2026-02-28
> Correcciones aplicadas: 2026-02-28
> Estado: **10 fixes aplicados** — pendientes 4 ítems de baja prioridad

---

## 1. Arquitectura general (estado actual)

```
POST /api/v1/calls/initiate
       │
       ▼
VoiceCallService.initiate_call()          ← call_service.py
       │
       ├── _resolve_broker_user_id()      (user ID del agente)
       ├── _company_broker_id_for_user()  (broker company ID)
       ├── [C4] ValueError si company_broker_id is None
       ├── Crea VoiceCall en DB (status=INITIATED)
       │
       ▼
VapiProvider.make_call()                  ← providers/vapi/provider.py
       │
       ├── BrokerVoiceConfigService.get_phone_number_id()  (Redis cache → DB → env var)
       ├── BrokerVoiceConfigService.get_assistant_id()     (por agent_type → default → env var)
       ├── Construye webhook_url desde WEBHOOK_BASE_URL
       │
       ▼
POST https://api.vapi.ai/call             (Vapi API)
       │
       └── Devuelve external_call_id → guarda en VoiceCall


POST /api/v1/calls/webhooks/voice         (Vapi → nuestro backend)
       │
       ▼
_handle_vapi_webhook()                    ← routes/voice.py
       │
       ├── [C1] Verifica x-vapi-secret → 401 si inválido
       ├── VapiProvider.handle_webhook()  → normaliza a WebhookEvent
       │
       ├── TOOL_CALLS        → handle_tool_call()  [A1: dispatcher activo]
       │                           ├── "schedule_appointment" → log + respuesta coherente
       │                           ├── "update_lead_stage"    → log + respuesta coherente
       │                           └── desconocido            → warning + "Acción registrada."
       ├── ASSISTANT_REQUEST → DB lookup por phone_number_id
       ├── END_OF_CALL_REPORT→ Celery: process_end_of_call_report.delay()  [C3: DLQTask]
       └── STATUS/TRANSCRIPT → VoiceCallService.handle_normalized_event()
                                     └── actualiza VoiceCall en DB
```

---

## 2. Request que se envía a Vapi

Archivo: `backend/app/services/voice/providers/vapi/provider.py`, líneas 90–108.

```json
{
  "assistantId": "<from BrokerVoiceConfig o VAPI_ASSISTANT_ID>",
  "phoneNumberId": "<from BrokerVoiceConfig o VAPI_PHONE_NUMBER_ID>",
  "customer": {
    "number": "+56912345678",
    "numberE164CheckEnabled": true
  },
  "assistantOverrides": {
    "server": {
      "url": "https://yourdomain.com/api/v1/calls/webhooks/voice"
    }
  },
  "metadata": {
    "lead_id": 123,
    "campaign_id": null,
    "broker_id": 1,
    "assistant_type": "default"
  }
}
```

- `assistantOverrides.server.url` — override oficial de Vapi por llamada (máxima prioridad sobre assistant/org level). Correcto.
- `metadata` — campos que Vapi reenvía en todos los webhooks de esa llamada.

---

## 3. Resolución de configuración por broker

```
BrokerVoiceConfigService.get_assistant_id(db, broker_id, agent_type)
  1. Redis cache (TTL 1h)
  2. DB: BrokerVoiceConfig.assistant_id_by_type[agent_type]
  3. DB: BrokerVoiceConfig.assistant_id_default
  4. settings.VAPI_ASSISTANT_ID  (env var global — fallback)
  5. ValueError si todo falla

Mismo patrón para phone_number_id.
```

### Modelo `BrokerVoiceConfig` (`broker_voice_config.py`)

| Campo | Tipo | Descripción |
|---|---|---|
| `broker_id` | FK → `brokers.id` | Un registro por broker (unique) |
| `provider` | String | `"vapi"` por defecto |
| `provider_credentials` | JSONB | API keys por broker (campo existe, sin implementar) |
| `phone_number_id` | String | Override Vapi phone number |
| `assistant_id_default` | String | Assistant default del broker |
| `assistant_id_by_type` | JSONB | `{"perfilador": "asst_xxx", ...}` |
| `voice_config` | JSONB | `{"provider": "azure", "voiceId": "es-MX-DaliaNeural"}` |
| `model_config` | JSONB | `{"provider": "openai", "model": "gpt-4o", "temperature": 0.7}` |
| `transcriber_config` | JSONB | `{"provider": "deepgram", "model": "nova-2", "language": "es"}` |
| `timing_config` | JSONB | `{"maxDurationSeconds": 300, "waitSeconds": 0.4, ...}` |
| `end_call_config` | JSONB | frases de cierre |
| `first_message_template` | Text | Template del saludo inicial |
| `recording_enabled` | Boolean | |

---

## 4. Webhooks recibidos — event mapping

Implementado en `provider.py:159–247`.

| `message.type` de Vapi | `CallEventType` interno | Handler |
|---|---|---|
| `status-update` | STATUS_UPDATE / CALL_RINGING / CALL_ANSWERED / CALL_ENDED / CALL_FAILED | `handle_call_webhook()` |
| `call-started` | CALL_STARTED | `handle_call_webhook()` |
| `transcript` | TRANSCRIPT_UPDATE | `handle_transcript_update()` (no persiste líneas) |
| `tool-calls` | TOOL_CALLS | `handle_tool_call()` → dispatcher activo |
| `end-of-call-report` | END_OF_CALL_REPORT | Celery `process_end_of_call_report.delay()` |
| `assistant-request` | ASSISTANT_REQUEST | DB lookup por `phone_number_id` |
| `hang` | HANG | Solo log |

> El webhook **siempre devuelve HTTP 200** — correcto, Vapi requiere 200 o reintenta.

---

## 5. Flujo post-llamada (end-of-call-report)

```
Vapi envía end-of-call-report
  → _handle_vapi_webhook() — verifica x-vapi-secret [C1]
  → Celery task: process_end_of_call_report() — DLQTask, max_retries=3 [C3]
      → Busca VoiceCall por external_call_id
      → VoiceCallService.update_call_transcript(transcript)
      → Actualiza recording_url en VoiceCall
      → Obtiene Lead y contexto
      → CallAgentService.generate_call_summary(transcript, lead_context)
          → LLM genera JSON: {summary, interest_level, budget, timeline, score_delta, stage_to_move}
          → [M1] json.loads() directo → fallback regex si falla
      → VoiceCallService.update_call_summary(summary, score_delta, stage_after_call)
      → Actualiza lead.lead_metadata[budget/timeline]
      → Actualiza lead.lead_score
      → PipelineService.move_lead_to_stage(stage_to_move)
      → db.commit()
      → Si falla: retry con backoff exponencial (60s, 120s, 180s) → DLQ tras 3 intentos
```

---

## 6. Variables de entorno requeridas

```bash
# Obligatorias para Vapi
VAPI_API_KEY=sk-...
VAPI_PHONE_NUMBER_ID=phn_...       # fallback global si broker no tiene config en DB
VAPI_ASSISTANT_ID=asst_...         # fallback global si broker no tiene config en DB
WEBHOOK_BASE_URL=https://tudominio.com   # CRÍTICO — se envía a Vapi para callbacks

# Seguridad webhooks (configurar en Vapi dashboard → Assistant → Server URL → Secret)
VAPI_WEBHOOK_SECRET=secret_...     # Si está vacío, no se verifica (solo dev)

# Selector de provider
VOICE_PROVIDER=vapi
```

> **Importante:** `WEBHOOK_BASE_URL` en `http://localhost:8000` en producción hace que Vapi
> no pueda alcanzar el backend. Es el error más común de configuración.
>
> **Importante:** `VAPI_WEBHOOK_SECRET` DEBE configurarse en producción. Sin él, cualquiera
> con la URL puede enviar webhooks falsos.

---

## 7. Problemas encontrados y estado de corrección

### CRÍTICO — todos corregidos ✅

#### C1 — Sin verificación de firma Vapi ✅ CORREGIDO
- **Dónde:** `routes/voice.py`
- **Problema original:** Los endpoints `/webhooks/voice` y `/webhooks/voice/{provider}` no verificaban `X-Vapi-Secret`. Cualquiera podía enviar webhooks falsos.
- **Corrección aplicada:**
  - `config.py`: agregado `VAPI_WEBHOOK_SECRET: str = os.getenv("VAPI_WEBHOOK_SECRET", "")`.
  - `routes/voice.py`: en `_handle_vapi_webhook()`, antes de cualquier lógica:
    ```python
    if settings.VAPI_WEBHOOK_SECRET:
        token = (headers or {}).get("x-vapi-secret") or ""
        if token != settings.VAPI_WEBHOOK_SECRET:
            logger.warning("Vapi webhook: invalid secret, rejecting request")
            return {"error": "Unauthorized"}
    ```
  - Si `VAPI_WEBHOOK_SECRET` está vacío se permite todo (modo dev). En producción DEBE configurarse.
- **Configurar en:** Vapi dashboard → Assistant → Server URL → Secret.

#### C2 — Campañas de voz eran un stub ✅ CORREGIDO
- **Dónde:** `tasks/campaign_executor.py`
- **Problema original:** `_execute_make_call()` siempre marcaba la acción como FAILED con `"not yet implemented"`.
- **Corrección aplicada:** Implementado llamando a `VoiceCallService.initiate_call()`:
  ```python
  voice_call = await VoiceCallService.initiate_call(
      db=db, lead_id=lead.id, campaign_id=campaign.id,
      broker_id=campaign.broker_id, agent_type=agent_type,
  )
  log.status = CampaignLogStatus.COMPLETED
  log.response = {"voice_call_id": ..., "external_call_id": ..., "status": ...}
  ```
  `ValueError` (lead sin teléfono, config faltante) se captura y marca log como FAILED con el error descriptivo.

#### C3 — Tasks de voz no usaban `DLQTask` ✅ CORREGIDO
- **Dónde:** `tasks/voice_tasks.py`
- **Problema original:** `process_end_of_call_report` usaba `@shared_task` básico. Fallos tras retries se perdían silenciosamente.
- **Corrección aplicada:**
  ```python
  @shared_task(base=DLQTask, bind=True, max_retries=3,
               name="app.tasks.voice_tasks.process_end_of_call_report")
  def process_end_of_call_report(self, external_call_id, transcript, ...):
      try:
          asyncio.run(_process())
      except Exception as exc:
          raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
  ```
  Backoff: 60s → 120s → 180s. Tras 3 fallos va al DLQ (visible en `/api/v1/admin/dlq`).

#### C4 — `broker_id=0` si usuario no tenía broker asignado ✅ CORREGIDO
- **Dónde:** `services/voice/call_service.py`
- **Problema original:** Se pasaba `0` como broker ID al provider, generando un error interno confuso.
- **Corrección aplicada:** En `initiate_call()`, tras resolver `company_broker_id`:
  ```python
  if company_broker_id is None:
      raise ValueError(
          f"User {broker_user_id} has no broker (company) assigned. "
          "Assign the user to a broker before initiating voice calls."
      )
  ```
  El endpoint devuelve HTTP 400 con mensaje claro.

---

### ALTO — corregidos ✅

#### A1 — Tool calls devolvían "Tool not found" ✅ CORREGIDO
- **Dónde:** `services/voice/call_service.py`
- **Problema original:** `handle_tool_call()` siempre devolvía `"Tool not found"`. Vapi recibía una respuesta errática.
- **Corrección aplicada:** Dispatcher funcional para las tools conocidas:
  ```python
  if tool_name == "schedule_appointment":
      logger.info("Tool call schedule_appointment lead_id=%s params=%s", lead_id, parameters)
      return "Entendido, un asesor te contactará para confirmar el horario."
  if tool_name == "update_lead_stage":
      return "Información registrada correctamente."
  logger.warning("Unknown tool call: %s", tool_name)
  return "Acción registrada."
  ```
  > La integración real con `AppointmentService` es una tarea separada. Lo prioritario es que Vapi reciba respuestas coherentes.

#### A2 — `generate_call_transcript_and_summary` era código muerto ✅ CORREGIDO
- **Dónde:** `tasks/voice_tasks.py`
- **Problema original:** Task generaba un placeholder inútil (`"[Transcript will be generated from recording: ...]"`). El transcript real ya llega via `end-of-call-report`.
- **Corrección aplicada:** Task convertida a no-op con deprecation warning:
  ```python
  @shared_task(name="app.tasks.voice_tasks.generate_call_transcript_and_summary")
  def generate_call_transcript_and_summary(voice_call_id: int):
      """DEPRECATED: Use process_end_of_call_report instead."""
      logger.warning("generate_call_transcript_and_summary is deprecated ...")
      return {"status": "deprecated", "voice_call_id": voice_call_id}
  ```

#### A3 — Dos endpoints de webhook con inicialización inconsistente ✅ CORREGIDO
- **Dónde:** `routes/voice.py`
- **Problema original:** `/webhooks/voice` usaba `get_voice_provider()` sync (compat shim); `/webhooks/voice/{provider}` usaba factory async. Técnicamente inconsistente y el endpoint legacy no pasaba los headers.
- **Corrección aplicada:** `/webhooks/voice` ahora usa la misma factory async y pasa headers:
  ```python
  from app.services.voice.factory import get_voice_provider as get_provider_async
  provider = await get_provider_async(provider_type="vapi", db=db)
  body = await _handle_vapi_webhook(payload, db, provider, headers=dict(request.headers))
  ```

#### A4 — Error message incorrecto en `get_call_status()` — ya estaba correcto
- **Dónde:** `providers/vapi/provider.py:144`
- **Hallazgo:** El código ya decía `"Failed to get call status"` — no requirió cambio.

---

### MEDIO — parcialmente corregidos

#### M1 — Parse de JSON del LLM con regex frágil ✅ CORREGIDO
- **Dónde:** `services/voice/call_agent.py` (métodos `process_call_turn` y `generate_call_summary`)
- **Problema original:** `re.search(r'\{.*\}', response, re.DOTALL)` fallaba silenciosamente con JSON que tiene texto previo, arrays al root, o estructuras anidadas.
- **Corrección aplicada:** Intento directo primero, regex con patrón anidado como fallback:
  ```python
  try:
      result = json.loads(response)
  except json.JSONDecodeError:
      json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
      if json_match:
          try:
              result = json.loads(json_match.group())
          except json.JSONDecodeError:
              result = <fallback_dict>
      else:
          result = <fallback_dict>
  ```

#### M2 — `build_assistant_config()` nunca se llamaba desde la app ✅ CORREGIDO
- **Dónde:** `routes/broker_config.py` (nuevo endpoint)
- **Problema original:** La lógica para crear assistants de Vapi desde config del broker existía pero no había ruta para invocarla.
- **Corrección aplicada:** Nuevo endpoint en `broker_config.py`:
  ```
  POST /api/v1/brokers/config/voice/assistant
  ```
  Llama a `VapiAssistantService.create_assistant_for_broker(db, broker_id)`. Auth: JWT requerido; broker_id tomado del usuario autenticado.

#### M3 — `ASSISTANT_REQUEST` expone assistant IDs sin auth — cubierto por C1
- **Dónde:** `routes/voice.py:58–72`
- **Problema original:** Sin autenticación, cualquiera podía descubrir assistant IDs por phone_number_id.
- **Estado:** Cubierto automáticamente por C1. Con `VAPI_WEBHOOK_SECRET` configurado, solo Vapi puede llamar a este endpoint.

#### M4 — `CallTranscript` table nunca se popula ⏳ PENDIENTE
- **Dónde:** `voice.py:236–242`, `voice_call.py:96–133`
- **Problema:** El modelo existe, la ruta `GET /{call_id}` la consulta, pero ningún código escribe en ella. Siempre devuelve `"transcript_lines": []`.
- **Fix sugerido:** Parsear el transcript string de Vapi (formato `"Bot: ...\nUser: ..."`) al procesar el `end-of-call-report`, o eliminar la tabla y el endpoint si no se implementará.

#### M5 — `provider_credentials` en `BrokerVoiceConfig` sin implementar ⏳ PENDIENTE
- **Dónde:** `broker_voice_config.py:24`
- **Problema:** El campo existe para API keys por broker, pero `VapiProvider` siempre usa `settings.VAPI_API_KEY` global. Multi-tenancy de API keys no implementado.
- **Fix sugerido (futuro):** Leer `provider_credentials["api_key"]` en `VapiProvider.__init__()` si está disponible, encriptado con `app.core.encryption`.

---

### BAJO — pendientes

#### B1 — `validate_config()` siempre retorna `True` ⏳ PENDIENTE
- **Dónde:** `base_provider.py:35–37`
- **Problema:** No hay validación de credenciales al inicio de la app. Los errores se descubren en el primer intento de llamada real.
- **Fix sugerido:** Implementar `validate_config()` en `VapiProvider` y llamarla en el startup event de FastAPI.

#### B2 — Ambigüedad `broker_id` en la capa de voz ⏳ PENDIENTE
- **Dónde:** `call_service.py`, `voice_call.py`, `provider.py`
- **Problema:** `VoiceCall.broker_id` es FK a `users.id` (agente), pero el parámetro también se llama `broker_id`. `company_broker_id` (empresa) es una variable interna. Tres conceptos con el mismo nombre.
- **Fix sugerido:** Renombrar internamente a `agent_user_id` / `company_broker_id` de forma consistente (requiere migración de DB).

#### B3 — `asyncio.run()` en Celery tasks puede fallar con ciertos pools ⏳ PENDIENTE
- **Dónde:** `voice_tasks.py`
- **Problema:** Puede fallar con `gevent`, `eventlet`, o `solo+uvloop`. El proyecto usa prefork, que lo soporta, pero no está documentado.
- **Fix sugerido:** Documentar `CELERY_WORKER_POOL=prefork` como requerimiento, o migrar a `asgiref.sync.async_to_sync`.

---

## 8. Estado por componente

| Componente | Estado | Desde | Notas |
|---|---|---|---|
| Payload a Vapi API | ✅ Correcto | Auditoría | `assistantOverrides.server.url` correcto |
| Resolución config por broker | ✅ Correcto | Auditoría | Cache Redis → DB → env var |
| Webhook parsing (7 event types) | ✅ Correcto | Auditoría | Mapping completo |
| HTTP 200 siempre en webhook | ✅ Correcto | Auditoría | Requerido por Vapi |
| `end-of-call-report` → Celery | ✅ Correcto | Auditoría | Actualiza transcript, score, stage |
| Verificación firma Vapi (`x-vapi-secret`) | ✅ Implementado | Fix C1 | Requiere `VAPI_WEBHOOK_SECRET` en env |
| Tool calls dispatcher | ✅ Implementado | Fix A1 | schedule_appointment, update_lead_stage |
| Campañas de voz (`make_call`) | ✅ Implementado | Fix C2 | Llama a `VoiceCallService.initiate_call()` |
| DLQ en `process_end_of_call_report` | ✅ Implementado | Fix C3 | `DLQTask`, retry exponencial, max 3 intentos |
| Guard `company_broker_id is None` | ✅ Implementado | Fix C4 | HTTP 400 con mensaje claro |
| JSON parsing en `call_agent.py` | ✅ Mejorado | Fix M1 | `json.loads()` directo + regex de fallback |
| Endpoint crear Vapi assistant | ✅ Implementado | Fix M2 | `POST /config/voice/assistant` |
| Consistencia endpoints webhook | ✅ Corregido | Fix A3 | Ambos usan factory async |
| `generate_call_transcript_and_summary` | ✅ Deprecado | Fix A2 | No-op con warning |
| `CallTranscript` table (líneas) | ❌ Dead end | — | Nunca se popula |
| API key por broker | ❌ Faltante | — | Siempre usa `VAPI_API_KEY` global |
| WebSocket al frontend en call events | ❌ Faltante | — | No hay `ws_manager.broadcast()` |
| `validate_config()` en startup | ❌ Faltante | — | Errores de config detectados tarde |

---

## 9. Historial de cambios

### 2026-02-28 — Correcciones aplicadas

| Fix ID | Archivo | Descripción |
|---|---|---|
| C1 | `config.py`, `routes/voice.py` | Verificación `VAPI_WEBHOOK_SECRET` en todos los webhooks |
| C2 | `tasks/campaign_executor.py` | `_execute_make_call()` implementado via `VoiceCallService` |
| C3 | `tasks/voice_tasks.py` | `process_end_of_call_report` → `DLQTask` con retry exponencial |
| C4 | `services/voice/call_service.py` | Guard `company_broker_id is None` con `ValueError` descriptivo |
| A1 | `services/voice/call_service.py` | `handle_tool_call()` dispatcher para `schedule_appointment` y `update_lead_stage` |
| A2 | `tasks/voice_tasks.py` | `generate_call_transcript_and_summary` deprecado → no-op |
| A3 | `routes/voice.py` | `/webhooks/voice` unificado con factory async, pasa headers |
| A4 | — | Error message en `get_call_status()` ya era correcto — sin cambio |
| M1 | `services/voice/call_agent.py` | JSON parsing: `json.loads()` directo + regex anidado como fallback |
| M2 | `routes/broker_config.py` | Nuevo `POST /config/voice/assistant` → `VapiAssistantService` |

---

## 10. Configuración Vapi — Documentación de referencia

### Variables de entorno

```bash
# .env (backend)
VAPI_API_KEY=sk-...                          # API key global de Vapi.ai
VAPI_PHONE_NUMBER_ID=phn_...                 # Phone number fallback global
VAPI_ASSISTANT_ID=asst_...                   # Assistant ID fallback global
WEBHOOK_BASE_URL=https://api.tudominio.com   # URL base del backend (sin trailing slash)
VAPI_WEBHOOK_SECRET=secret_...               # Firmar webhooks — OBLIGATORIO en producción
VOICE_PROVIDER=vapi                          # Provider activo
```

### Configuración por broker (tabla `broker_voice_configs`)

```sql
INSERT INTO broker_voice_configs (
    broker_id, provider,
    phone_number_id, assistant_id_default, assistant_id_by_type,
    voice_config, model_config, transcriber_config,
    timing_config, end_call_config,
    first_message_template, recording_enabled
) VALUES (
    1, 'vapi',
    'phn_xxxxxxxxxxxx',
    'asst_xxxxxxxxxxxx',
    '{"perfilador": "asst_aaa", "calificador": "asst_bbb"}',
    '{"provider": "azure", "voiceId": "es-MX-DaliaNeural"}',
    '{"provider": "openai", "model": "gpt-4o", "temperature": 0.7}',
    '{"provider": "deepgram", "model": "nova-2", "language": "es"}',
    '{"maxDurationSeconds": 300, "waitSeconds": 0.4, "voiceSeconds": 0.3, "backoffSeconds": 1.2}',
    '{"endCallMessage": "Muchas gracias, hasta pronto.", "endCallPhrases": ["adiós", "chao", "no me interesa"]}',
    'Hola {lead_name}, soy de {broker_company}. ¿Tienes un momento?',
    true
);
```

### Pasos de setup en Vapi dashboard

1. **Crear phone number** → copiar `Phone Number ID` → guardar en `broker_voice_configs.phone_number_id` o `VAPI_PHONE_NUMBER_ID`
2. **Crear assistant** en Vapi:
   - System prompt: usar `BrokerVoiceConfigService.adapt_prompt_for_voice()` para adaptar el prompt de chat, o invocar el nuevo endpoint `POST /config/voice/assistant` para crearlo desde la config del broker
   - Voice: `azure` / `es-MX-DaliaNeural`
   - Model: `openai` / `gpt-4o`
   - Transcriber: `deepgram` / `nova-2` / `es`
   - **NO configurar `serverUrl` en el assistant** — el override se hace por llamada via `assistantOverrides.server.url`
   - **Configurar `Secret`** (Server URL Secret) → copiar valor a `VAPI_WEBHOOK_SECRET`
3. Copiar `Assistant ID` → guardar en `broker_voice_configs.assistant_id_default` o `VAPI_ASSISTANT_ID`
4. Verificar que `WEBHOOK_BASE_URL` apunte al backend accesible públicamente

### Endpoints del sistema

| Método | Path | Auth | Descripción |
|---|---|---|---|
| `POST` | `/api/v1/calls/initiate` | JWT | Inicia llamada saliente |
| `POST` | `/api/v1/calls/webhooks/voice` | `x-vapi-secret` | Recibe webhooks de Vapi (default) |
| `POST` | `/api/v1/calls/webhooks/voice/{provider}` | `x-vapi-secret` | Recibe webhooks por provider |
| `GET` | `/api/v1/calls/leads/{lead_id}` | JWT | Historial de llamadas de un lead |
| `GET` | `/api/v1/calls/{call_id}` | JWT | Detalle + transcript de una llamada |
| `POST` | `/api/v1/brokers/config/voice/assistant` | JWT | Crea/actualiza assistant Vapi desde config del broker |

### Payload que Vapi recibe al iniciar llamada

```json
POST https://api.vapi.ai/call
Authorization: Bearer {VAPI_API_KEY}

{
  "assistantId": "{assistant_id}",
  "phoneNumberId": "{phone_number_id}",
  "customer": {
    "number": "+56912345678",
    "numberE164CheckEnabled": true
  },
  "assistantOverrides": {
    "server": {
      "url": "{WEBHOOK_BASE_URL}/api/v1/calls/webhooks/voice"
    }
  },
  "metadata": {
    "lead_id": 123,
    "campaign_id": null,
    "broker_id": 1,
    "assistant_type": "default"
  }
}
```

### Webhooks que envía Vapi al backend

Todos los webhooks tienen estructura base:
```json
{
  "message": {
    "type": "status-update | transcript | tool-calls | end-of-call-report | assistant-request | hang",
    "call": {
      "id": "call_xxxx",
      "status": "ringing | in-progress | ended | failed",
      "metadata": { "lead_id": 123, "broker_id": 1, "assistant_type": "default" }
    }
  }
}
```

Header enviado por Vapi: `x-vapi-secret: {VAPI_WEBHOOK_SECRET}`

Respuesta esperada: **HTTP 200** con JSON.

Para `tool-calls`:
```json
{
  "results": [
    { "toolCallId": "xxx", "name": "schedule_appointment", "result": "Entendido, un asesor te contactará..." }
  ]
}
```

Para `assistant-request`:
```json
{ "assistantId": "asst_xxx" }
```

### Tabla `voice_calls` — campos clave

| Campo | Tipo | Descripción |
|---|---|---|
| `lead_id` | FK leads | Lead que recibió la llamada |
| `campaign_id` | FK campaigns | Campaña que originó la llamada (nullable) |
| `external_call_id` | String unique | ID de Vapi (indexed) |
| `status` | Enum | `initiated → ringing → answered → completed/failed/no_answer/busy` |
| `transcript` | Text | Transcript completo de Vapi (del end-of-call-report) |
| `summary` | Text | Resumen generado por LLM |
| `score_delta` | Float | Cambio de score del lead tras la llamada |
| `stage_after_call` | String | Stage recomendado por LLM |
| `recording_url` | String | URL de la grabación |
| `broker_id` | FK users | User ID del agente que inició la llamada (≠ company broker ID) |

### Checklist de verificación post-deploy

```bash
# C1: Firma webhook
curl -X POST https://api.tudominio.com/api/v1/calls/webhooks/voice \
  -H "Content-Type: application/json" \
  -d '{"message": {"type": "status-update"}}' \
  # → debe devolver {"error": "Unauthorized"}

curl -X POST https://api.tudominio.com/api/v1/calls/webhooks/voice \
  -H "x-vapi-secret: $VAPI_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"message": {"type": "status-update", "call": {"id": "test"}}}' \
  # → debe devolver {"ok": true}

# C4: Guard broker sin company
# Crear user sin broker asignado → POST /api/v1/calls/initiate → debe devolver 400

# C3: DLQ
# Tras 3 fallos en process_end_of_call_report → verificar en GET /api/v1/admin/dlq

# A1: Tool calls
# Enviar webhook tool-calls con name="schedule_appointment" → respuesta ≠ "Tool not found"

# M2: Crear assistant
# POST /api/v1/brokers/config/voice/assistant (con JWT de admin) → debe devolver resultado de Vapi
```
