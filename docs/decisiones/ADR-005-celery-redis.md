# ADR-005: Celery + Redis para tareas asíncronas

> Estado: Aceptada
> Fecha: 2026-04-17

## Contexto

El sistema necesita procesar tareas en background que no pueden bloquear respuestas HTTP: análisis de sentiment de mensajes, ejecución de campañas de outreach, scoring de leads, envío de mensajes por Telegram/WhatsApp, y llamadas de voz programadas via VAPI.

Estas tareas pueden fallar por problemas transitorios (timeout de API, conexión a DB) y necesitan retry automático con backoff. También se requiere visibilidad sobre tareas fallidas para investigación y reprocesamiento manual.

## Decisión

Usar Celery como framework de tareas asíncronas con Redis como message broker. Cada tarea hereda de `DLQTask` (base en `tasks/base.py`) que implementa:
- Retry automático con exponential backoff
- Dead Letter Queue (DLQ) para tareas que agotan reintentos
- Logging estructurado para debugging
- Métricas de ejecución

Tareas principales:
- `campaign_executor.py`: Ejecución de campañas de mensaje masivo
- `scoring_tasks.py`: Recalculación de scores de leads
- `telegram_tasks.py`: Envío de mensajes Telegram
- `voice_tasks.py`: Iniciación y monitoreo de llamadas VAPI
- `dlq_tasks.py`: Operaciones de reprocesamiento y descarte del DLQ

## Consecuencias

**Pros:**
- Framework maduro con amplia documentación y comunidad
- Excelente monitoreo con Flower (dashboard web para Celery)
- Soporte nativo para Dead Letter Queue y retry con backoff
- Integración con Redis (ya usado para cache/sessions)
- Task routing permite diferentes colas para diferentes prioridades
- Scheduling periódico con Celery Beat para tareas cron
- Logging centralizado facilita debugging de failures

**Contras:**
- Infraestructura adicional: Redis como broker separado
- Complejidad operacional: queues, workers, beat, flower
- Debugging harder: stack traces en logs de workers, no en request
-货物运送语义: at-least-once delivery requiere idempotencia en tareas
- Actualizaciones de schema pueden romper tareas en vuelo
- Monitoreo adicional necesario para detectar tareas huérfanas
