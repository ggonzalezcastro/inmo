---
title: Changelog
version: 1.1.0
date: 2026-02-22
author: Equipo Inmo
---

# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

## [1.1.0] - 2026-02-22

### Añadido

#### Sistema Multi-Agente Especializado (TASK-026)
- `AgentSupervisor` — enrutador stateless con guard de máx. 3 handoffs
- `QualifierAgent` — recopila datos del lead, aplica regla DICOM, cede al SchedulerAgent cuando el lead está calificado
- `SchedulerAgent` — propone y confirma visitas a proyectos, cede al FollowUpAgent al confirmar cita
- `FollowUpAgent` — seguimiento post-visita y recolección de referidos
- Protocolo `HandoffSignal` con `context_updates` entre agentes
- Feature flag `MULTI_AGENT_ENABLED` para rollout progresivo sin romper el orquestador existente
- 27 tests unitarios con mocks de LLM (sin llamadas reales) en `tests/services/test_multi_agent.py`
- Documentación en `docs/architecture/multi_agent.md`

#### Base de Conocimiento RAG con pgvector (TASK-024)
- Modelo `KnowledgeBase` con embeddings 768-dim (Gemini `text-embedding-004`)
- Extensión `pgvector` con índice `IVFFlat` para búsqueda semántica por coseno
- API CRUD en `/api/v1/kb`: listar, buscar semánticamente, agregar con auto-embedding, actualizar, eliminar
- Migración `m4h5i6j7k8l9_add_knowledge_base_table.py`

#### Framework de Evaluación de Calidad (TASK-025)
- Dataset de 51 conversaciones etiquetadas en `tests/evals/dataset/conversations.json`
- `DicomRuleMetric` — métrica determinista (regex) que detecta violaciones de la regla DICOM sin LLM
- `TaskCompletionMetric` — métrica determinista que verifica cumplimiento de acciones esperadas (30+ patrones)
- Tests de LLM-judge opcionales vía `deepeval` (`EVAL_LLM_ENABLED=true`)
- Baselines registrados en `docs/testing/eval_baseline.md` (fecha: 2026-02-22)
- 26 tests que pasan sin ninguna API key externa

#### WebSocket para Actualizaciones en Tiempo Real (TASK-027)
- `ConnectionManager` en `app/core/websocket_manager.py` — asyncio-safe, conexiones por `broker_id`
- Endpoint `GET /ws/{broker_id}` con autenticación JWT
- Tipos de evento: `new_message`, `stage_changed`, `lead_assigned`, `lead_hot`, `typing`
- Broadcast automático en cambios de etapa del pipeline (`move_lead_to_stage`)

#### Dead Letter Queue para Celery (TASK-029)
- `DLQTask` — clase base para todas las tareas Celery; enruta fallos finales a DLQ automáticamente
- `DLQManager` en `app/tasks/dlq.py` — backed en Redis, push/pop/reintento/descarte
- `app/tasks/dlq_tasks.py` — tareas Celery para reintentar y descartar ítems de la DLQ en bulk
- Endpoints admin en `app/routes/admin_tasks.py`: listar, reintentar, descartar ítems DLQ

#### Prompt Caching para Gemini (TASK-028)
- `PromptCacheManager` en `app/services/llm/prompt_cache.py`
- Una entrada de caché por `(broker_id, prompt_hash)` almacenada en Redis
- Reducción estimada de ~75% en tokens de entrada para el system prompt del broker
- Feature flag `GEMINI_CONTEXT_CACHING_ENABLED` (default: `false`)
- Estadísticas de hit/miss expuestas en `/health`

#### Documentación de API (TASK-030)
- 16 tags OpenAPI con descripciones en `app/main.py`
- Colección Postman completa en `docs/api/postman_collection.json`
- Documentación de payloads de webhooks en `docs/api/webhooks.md` (Telegram, WhatsApp, VAPI)
- Ejemplos `json_schema_extra` en schemas Pydantic clave

---

## [1.0.0] - 2026-02-21

### Añadido

#### Arquitectura Multi-Provider de Voz
- Abstracción `BaseVoiceProvider` con Strategy Pattern
- Factory para resolución dinámica de proveedores por broker
- Implementación de `VapiProvider` (VAPI.ai)
- Implementación de `BlandProvider` (Bland AI)
- Tipos normalizados: `WebhookEvent`, `MakeCallRequest`, `CallStatusResult`
- Webhook dinámico `/webhooks/voice/{provider_name}`
- Configuración `provider` y `provider_credentials` en `BrokerVoiceConfig`
- Migración de base de datos para nuevos campos de voz

#### Reorganización de Services
- Servicios organizados por dominio en subdirectorios
- Directorio `shared/` para servicios transversales
- Eliminación de 15 archivos facade redundantes
- Eliminación de 3 archivos duplicados
- `LLMServiceFacade` movido a `llm/facade.py`

#### Sistema de Chat Multi-Canal
- Abstracción `BaseChatProvider`
- Proveedor de Telegram
- Proveedor de WhatsApp
- `ChatOrchestratorService` para flujo unificado
- Modelo `ChatMessage` con soporte multi-proveedor
- Modelo `BrokerChatConfig` para configuración por broker

#### Pipeline de Ventas
- Etapas: entrada → perfilamiento → calificación → agendado → seguimiento → ganado/perdido
- Auto-avance basado en datos del lead
- Métricas por etapa
- Detección de leads inactivos

#### Campañas Automatizadas
- CRUD de campañas con steps
- Triggers: manual, score, cambio de etapa, inactividad
- Acciones: enviar mensaje, llamar, agendar, mover etapa
- Ejecución vía Celery
- Estadísticas y logs

#### Sistema de Citas
- Integración con Google Calendar
- Google Meet links automáticos
- Disponibilidad de agentes
- Booking vía chat IA (function calling)
- Estados: scheduled, confirmed, cancelled, completed, no_show

#### LLM Multi-Provider
- Soporte para Google Gemini, Anthropic Claude, OpenAI GPT
- Factory con selección por configuración
- Análisis de mensajes y generación de respuestas
- Extracción automática de datos del lead

#### Scoring de Leads
- Score calculado: base + comportamiento + engagement + financiero
- Clasificación automática: cold, warm, hot
- Configuración de pesos por broker
- Recalcuación diaria vía Celery Beat

#### Autenticación y Autorización
- JWT con bcrypt
- Roles: SUPERADMIN, ADMIN, AGENT
- Rate limiting por IP y endpoint
- Multi-tenancy por broker_id

#### Documentación
- Documentación profesional en `/docs`
- Diagramas Mermaid (arquitectura, ERD, flujo de datos, componentes)
- ADRs (Architecture Decision Records)
- Casos de uso UML
- Documentación de API endpoints
- Guías de inicio, desarrollo y despliegue

### Cambios

- Migración de imports directos a subpaquetes de services
- `VoiceCallService.handle_normalized_event()` acepta `WebhookEvent` genérico
- Configuración centralizada en `app/core/config.py` con Pydantic Settings

---

## [0.1.0] - 2025-01-01

### Añadido

- Proyecto inicial con FastAPI y React
- CRUD básico de leads
- Integración con Telegram
- Integración con VAPI (acoplada)
- Integración con Google Gemini
- Pipeline básico de ventas
- Docker Compose para desarrollo
