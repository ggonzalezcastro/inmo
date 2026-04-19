# Arquitectura Celery Tasks

**Fecha:** 17 de Abril 2026  
**Proyecto:** inmo CRM  
**Módulo:** Backend — Cola de tareas asíncronas

---

## Visión General

El sistema utiliza **Celery** con **Redis** como broker y result backend para ejecutar tareas asíncronas:

- Procesamiento de campañas de leads (envío de mensajes, llamadas, cambios de etapa)
- Análisis de sentimiento posterior a mensajes entrantes
- Programación de tareas recurrentes via Celery Beat

```
┌─────────────────────────────────────────────────────────────┐
│                     Celery Application                        │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────┐  │
│  │  Celery Beat │  │  Celery Worker(s)│  │  Dead Letter   │  │
│  │  (scheduler) │  │                  │  │  Queue (DLQ)  │  │
│  └──────────────┘  └──────────────────┘  └────────────────┘  │
│         │                   │                    │            │
└─────────┼───────────────────┼────────────────────┼────────────┘
          │                   │                    │
          ▼                   ▼                    ▼
    ┌───────────┐      ┌───────────┐        ┌───────────┐
    │  Redis    │      │  Redis    │        │  Redis    │
    │  /1 broker│      │  /2 result│        │  /3 DLQ   │
    └───────────┘      └───────────┘        └───────────┘
```

---

## Registered Tasks

### analyze_sentiment

```python
@shared_task(
    name="app.tasks.sentiment_tasks.analyze_sentiment",
    base=DLQTask,
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    ignore_result=True,
)
def analyze_sentiment(self, lead_id, message, broker_id, channel="webchat"):
```

**Propósito:** Análisis de sentimiento con ventana deslizante (sliding window) sobre el historial de mensajes del lead.

**Comportamiento:**
- Se ejecuta después de cada mensaje entrante (fire-and-forget)
- **No bloquea** el pipeline de respuesta IA
- Canal por defecto: `webchat`

**Parámetros:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `lead_id` | `str` | ID del lead al que pertenece el mensaje |
| `message` | `str` | Contenido del mensaje entrante |
| `broker_id` | `str` | ID del broker (multi-tenant) |
| `channel` | `str` | Canal de origen (`webchat`, `telegram`, `whatsapp`) |

**Retry:** 2 intentos con delay de 30s entre intentos.

---

### execute_campaign_step

```python
@shared_task(
    name="app.tasks.campaign_executor.execute_campaign_step",
    base=DLQTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def execute_campaign_step(self, campaign_id, lead_id, step_number):
```

**Propósito:** Ejecuta un paso individual de una campaña aplicada a un lead.

**Comportamiento:**
1. Ejecuta la acción definida en el paso (`send_message`, `make_call`, `update_stage`)
2. Calcula el delay del siguiente paso: `next_step.delay_hours * 3600`
3. Programa el siguiente paso con ese countdown

**Parámetros:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `campaign_id` | `str` | ID de la campaña |
| `lead_id` | `str` | ID del lead |
| `step_number` | `int` | Número de paso a ejecutar (1-indexed) |

**Retry:** 3 intentos con delay de 60s entre intentos.

---

### execute_campaign_for_lead

```python
@shared_task(
    name="app.tasks.campaign_executor.execute_campaign_for_lead",
    base=DLQTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def execute_campaign_for_lead(self, campaign_id, lead_id):
```

**Propósito:** Inicia una campaña para un lead específico.

**Comportamiento:**
- Aplica la campaña al lead
- Programa el paso 1 de forma inmediata usando el `delay_hours` del primer paso como countdown inicial

**Parámetros:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `campaign_id` | `str` | ID de la campaña |
| `lead_id` | `str` | ID del lead |

**Retry:** 3 intentos con delay de 60s entre intentos.

---

### check_trigger_campaigns

```python
@shared_task(name="app.tasks.campaign_executor.check_trigger_campaigns")
def check_trigger_campaigns():
```

**Propósito:** Evalúa periódicamente los triggers de campañas activas.

**Comportamiento:**
1. Consulta campañas con estado `ACTIVE`
2. Para cada trigger, encuentra leads elegibles según las condiciones
3. Aplica la campaña a cada lead elegible

**Frecuencia:** Cada hora (via Celery Beat).

---

## Acciones de Paso de Campaña

Las acciones disponibles para cada paso de campaña:

### send_message

Envía un mensaje al lead a través del canal configurado.

```python
# Canales soportados:
# - telegram:  → TelegramService.send_message()
# - whatsapp:   → WhatsAppService.send_message()
# - ai:        → Genera respuesta IA sin enviar (para testing/debug)
```

### make_call

Inicia una llamada de voz via VAPI.

```python
VoiceCallService.initiate_call(lead_id=lead_id, broker_id=broker_id)
```

### schedule_meeting

> ⚠️ **NOT YET IMPLEMENTED** — Reservado para futura integración con Google Calendar.

### update_stage

Avanza al lead a una nueva etapa del pipeline.

```python
PipelineService.move_lead_to_stage(lead_id=lead_id, new_stage=stage, broker_id=broker_id)
```

---

## Condiciones de Trigger

### LEAD_SCORE

```python
{"score_min": int, "score_max": int}
```

El lead es elegible si su score está dentro del rango `[score_min, score_max]`.

### STAGE_CHANGE

```python
{"stage": "perfilamiento" | "calificacion_financiera" | ...}
```

El lead es elegible cuando cambia a la etapa especificada.

### INACTIVITY

```python
{"inactivity_days": int}
```

El lead es elegible si no ha tenido actividad en los últimos `inactivity_days` días.

### MANUAL

Aplica solo cuando se ejecuta manualmente via API. No se evalúa en `check_trigger_campaigns`.

---

## Celery Beat Schedule

```python
CELERY_BEAT_SCHEDULE = {
    "check_trigger_campaigns": {
        "task": "app.tasks.campaign_executor.check_trigger_campaigns",
        "schedule": crontab(minute=0),  # Cada hora en punto
    },
}
```

**Tareas bajo demanda (no programadas):**

| Task | Disparo |
|------|---------|
| `analyze_sentiment` | Post inbound message |
| `execute_campaign_step` | Después de aplicar campaña a lead (step N→N+1) |
| `execute_campaign_for_lead` | Aplicación manual de campaña |

---

## Dead Letter Queue (DLQ)

### Mecanismo

Todas las tareas heredan de `DLQTask`, una clase base que intercepta fallos:

```python
class DLQTask(Task):
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # Invocado cuando max_retries se agota
        # Registra en DLQ:
        #   - task_name
        #   - args
        #   - kwargs
        #   - exception
        #   - traceback
        #   - retries actuales
        #   - timestamp
        push_to_dlq(task_name, args, kwargs, exception, traceback, retries)
        super().on_failure(exc, task_id, args, kwargs, einfo)
```

### Estructura DLQ (Redis)

```
Key:  dlq:entries
Type: Sorted Set (score = failed_at timestamp)
```

**Campos de cada entrada:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | `str` | UUID único |
| `task_name` | `str` | Nombre completo de la tarea |
| `args` | `list` | Argumentos posicionales |
| `kwargs` | `dict` | Argumentos nombrados |
| `exception` | `str` | Mensaje de la excepción |
| `traceback` | `str` | Stack trace completo |
| `retries` | `int` | Número de reintentos intentados |
| `failed_at` | `float` | Timestamp UNIX del fallo |

### Operaciones DLQ

| Operación | Descripción |
|-----------|-------------|
| `push` | Agrega entrada a DLQ tras agotar retries |
| `list_failed(offset, limit)` | Lista entradas con paginación |
| `retry(task_id)` | Reenvía la tarea con argumentos originales |
| `delete(task_id)` | Elimina entrada de DLQ |
| `count()` | Retorna total de entradas en DLQ |

### API de Administración

Endpoints en `app/routes/admin_tasks.py` para gestión via UI:

```
GET  /admin/dlq              → Lista entradas (paginated)
POST /admin/dlq/{id}/retry   → Reintentar tarea
DELETE /admin/dlq/{id}       → Descartar entrada
GET  /admin/dlq/count         → Total de entradas
```

---

## Configuración Redis Broker

```python
# Variables de entorno
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
```

| Slot | Uso |
|------|-----|
| `/1` | Broker — cola de mensajes Celery |
| `/2` | Result Backend — estado de tareas |
| `/3` | DLQ (implementación propia, no Celery) |

---

## Flujo de Error

```
Task ejecutándose
        │
        ▼
   ┌─────────┐
   │  ¿Éxito?│
   └────┬────┘
    Yes │ No
        ▼         ▼
   Done    max_retries
             agotados?
             │      │
            No    Yes
             │      │
             ▼      ▼
        retry()   on_failure()
                     │
                     ▼
               push_to_dlq()
                     │
                     ▼
               DLQ entry created
                     │
                     ▼
          Admin puede reintentar o descartar
```

---

## Changelog

### 2026-04-17

- Documento creado con arquitectura completa de Celery Tasks
- Incluidos: `analyze_sentiment`, `execute_campaign_step`, `execute_campaign_for_lead`, `check_trigger_campaigns`
- Documentado DLQ con estructura Redis y operaciones
- Agregado flujo de error completo
