# Observabilidad y Monitoring

> Última actualización: 2026-04-18

## Overview

El sistema tiene múltiples capas de observabilidad para ayudarte a entender qué está pasando y diagnosticar problemas.

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend                            │
│  WebSocket events → Real-time UI updates               │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                     Backend                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   FastAPI   │  │   Celery    │  │  OpenTelemetry│   │
│  │  (traces)   │  │  (tasks)   │  │  (spans)     │   │
│  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    ┌──────────┐   ┌──────────┐   ┌──────────┐
    │PostgreSQL│   │  Redis   │   │  Jaeger  │
    │(llm_calls│   │(cache,   │   │(traces)  │
    │agent_evt)│   │ DLQ)     │   │          │
    └──────────┘   └──────────┘   └──────────┘
```

---

## OpenTelemetry

### Configuración

```bash
# Habilitar OTEL
OTEL_ENABLED=true
OTEL_SERVICE_NAME=inmo-backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318
```

### Spans configurados

```python
# Backend/app/services/llm/facade.py
with trace_span("llm.qualify", {"provider": pname, "model": model}):
    result = await provider.generate_json(...)

with trace_span("llm.chat", {"provider": pname, "model": model}):
    result = await provider.generate_with_tools(...)
```

### Ver traces en Jaeger

1. Accede a http://localhost:16686 (Jaeger UI)
2. Busca por `service=inmo-backend`
3. Filtra por operación (llm.qualify, llm.chat, etc.)

---

## Sentry (Error Tracking)

### Configuración

```bash
# En backend/.env
SENTRY_DSN=https://xxxxx@sentry.io/xxxxx
```

### Errores capturados

- Excepciones no manejadas en endpoints
- Errores de LLM (cuandofallback también falla)
- Errores de Celery tasks (antes de ir a DLQ)
- Errores de conexión a servicios externos

### Uso en código

```python
from sentry_sdk import capture_exception, capture_message

try:
    await do_something()
except Exception as e:
    capture_exception(e)
    raise

capture_message("User performed action", level="info")
```

---

## LLM Call Logging

### Tabla llm_calls

Cada llamada al LLM se registra en la tabla `llm_calls`:

```sql
SELECT
    id,
    provider,
    model,
    call_type,
    input_tokens,
    output_tokens,
    estimated_cost_usd,
    latency_ms,
    used_fallback,
    error,
    created_at
FROM llm_calls
WHERE broker_id = 1
ORDER BY created_at DESC
LIMIT 100;
```

### Campos principales

| Campo | Descripción |
|-------|-------------|
| `provider` | gemini, claude, openai |
| `model` | Modelo específico usado |
| `call_type` | qualification, chat_response, improve_message |
| `input_tokens` | Tokens de entrada (estimados o reales) |
| `output_tokens` | Tokens de salida (estimados o reales) |
| `estimated_cost_usd` | Costo estimado en USD |
| `latency_ms` | Latencia total de la llamada |
| `used_fallback` | Si usó el provider fallback |
| `error` | Mensaje de error si falló |

### Dashboard de costos

```bash
# GET /api/v1/admin/costs/summary?period=month&broker_id=1
{
  "total_cost_usd": 12.45,
  "cost_by_provider": {"gemini": 10.00, "claude": 2.45},
  "cost_by_call_type": {"chat_response": 8.00, "qualification": 4.45},
  "total_calls": 1523,
  "fallback_rate": 0.02,
  "avg_latency_ms": 1200
}
```

---

## Agent Event Logger

### Tabla agent_events

Para debugging de conversaciones con agentes:

```sql
SELECT
    id,
    event_type,
    agent_type,
    lead_id,
    details,
    created_at
FROM agent_events
WHERE lead_id = 123
ORDER BY created_at DESC;
```

### Tipos de eventos

| Evento | Descripción |
|--------|-------------|
| `agent_selected` | Un agente fue seleccionado para procesar |
| `handoff` | Se transfirió a otro agente |
| `qualification` | Se extrajeron campos de calificación |
| `sentiment_analyzed` | Se analizó el sentimiento |
| `llm_call` | Se hizo una llamada al LLM |

---

## WebSocket Events para Debugging

### Conectar al WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/1/123');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('WS Event:', data.type, data.data);
};
```

### Eventos disponibles

| Evento | Cuándo ocurre |
|--------|---------------|
| `new_message` | Nuevo mensaje de chat |
| `ai_response` | IA generó respuesta |
| `stage_changed` | Lead cambió de etapa |
| `lead_assigned` | Lead asignado a agente |
| `lead_hot` | Lead cambió a estado HOT |
| `human_mode_changed` | Toma/release de control humano |
| `typing` | Lead está escribiendo |
| `lead_frustrated` | Sentiment muy alto detectado |

---

## Celery Monitoring

### Flower (Monitor web)

```bash
# Instalar
pip install flower

# Correr
celery -A app.celery_app flower --port=5555
```

Accede a http://localhost:5555 para ver:
- Tasks activas y pendientes
- Workers conectados
- Historial de tasks
- Retry counts

### Dead Letter Queue (DLQ)

Cuando una task falla después de max_retries, va al DLQ.

```bash
# Ver DLQ via API
GET /api/v1/admin/tasks/failed

# Reintentar una task
POST /api/v1/admin/tasks/{id}/retry

# Descartar una task
DELETE /api/v1/admin/tasks/{id}
```

### Tasks Registradas

| Task | Descripción |
|------|-------------|
| `app.tasks.sentiment_tasks.analyze_sentiment` | Análisis async de sentiment |
| `app.tasks.campaign_executor.execute_campaign_step` | Ejecutar paso de campaña |
| `app.tasks.campaign_executor.check_trigger_campaigns` | Verificar campaigns hourly |

---

## Health Checks

### Endpoint

```bash
GET /api/v1/health
```

### Respuesta

```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "celery": "available"
}
```

### Docker Health Check

```yaml
# docker-compose.yml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

---

## Logging Estructurado

### Formato

```json
{
  "timestamp": "2026-04-18T10:30:00Z",
  "level": "INFO",
  "logger": "app.services.agents.supervisor",
  "message": "Routing to QualifierAgent",
  "lead_id": 123,
  "broker_id": 1,
  "stage": "entrada"
}
```

### Logs clave a monitorear

| Logger | Qué buscar |
|--------|-----------|
| `app.services.agents.supervisor` | Selección de agente, handoffs |
| `app.services.chat.orchestrator` | Flujo de mensajes, errores |
| `app.services.sentiment` | Análisis de sentiment, escalaciones |
| `app.services.llm` | Llamadas LLM, errores, fallbacks |
| `app.tasks` | Tasks de Celery, retries, DLQ |

---

## Comandos Rápidos

### Ver logs del backend

```bash
docker-compose logs -f backend
```

### Ver logs de Celery

```bash
docker-compose logs -f celery
```

### Ver queries lentas en PostgreSQL

```sql
SELECT * FROM pg_stat_activity
WHERE state = 'active'
AND query_start < NOW() - INTERVAL '5 seconds';
```

### Ver uso de memoria Redis

```bash
redis-cli info memory
```

### Limpiar cache de Redis

```bash
redis-cli FLUSHALL
```

---

## Changelog

| Fecha | Descripción |
|--------|-------------|
| 2026-04-18 | Creación del documento de observabilidad |
| 2026-04-17 | Agregada sección de Sentry |
