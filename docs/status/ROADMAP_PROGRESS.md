# Roadmap Progress — AI Lead Agent Pro

**Última Actualización:** 2026-02-22

---

## Estado General

| Sprint | Periodo | Estado |
|--------|---------|--------|
| Sprint 1 | Ene 2025 | ✅ Completado |
| Sprint 2 | Feb 2026 (semana 1-2) | ✅ Completado |
| Sprint 3 / Backlog | Feb 2026 (semana 3-4) | ✅ Completado |

---

## Sprint 1 — Base del Sistema ✅

- ✅ FastAPI async + SQLAlchemy 2.0
- ✅ PostgreSQL + Redis + Celery
- ✅ JWT multi-tenant por broker
- ✅ CRUD de leads
- ✅ Integración Telegram Bot
- ✅ Integración Google Gemini
- ✅ Pipeline de ventas con 8 etapas
- ✅ Sistema de scoring (base + comportamiento + engagement)
- ✅ Docker Compose para desarrollo

---

## Sprint 2 — Calidad y Extensibilidad ✅

| Task | Descripción |
|------|-------------|
| TASK-006 | Tabla de llamadas LLM con costos |
| TASK-010 | Temperaturas por tipo de llamada LLM |
| TASK-012 | Tests de voice providers |
| TASK-013 | Lockfile con uv |
| TASK-015 | Versionado de prompts por broker |
| TASK-016 | Few-shot examples en prompts |
| TASK-019 | CI/CD (pendiente de configurar) |
| TASK-023 | Dashboard de costos LLM |
| TASK-024 | RAG con pgvector |
| TASK-027 | WebSocket tiempo real |
| TASK-028 | Gemini prompt caching |
| TASK-029 | Dead Letter Queue Celery |

---

## Sprint 3 / Backlog — IA Avanzada ✅

| Task | Descripción | Entregables clave |
|------|-------------|-------------------|
| **TASK-024** | Base de conocimiento RAG con pgvector | `models/knowledge_base.py`, `routes/knowledge_base.py`, migración `m4h5...` |
| **TASK-025** | Eval framework con deepeval | `tests/evals/` — 51 conversaciones, `DicomRuleMetric`, `TaskCompletionMetric`, 26 tests, baselines |
| **TASK-026** | Arquitectura multi-agente | `services/agents/` — 4 agentes, supervisor, 27 tests, `docs/architecture/multi_agent.md` |
| **TASK-027** | WebSocket actualizaciones tiempo real | `core/websocket_manager.py`, `routes/ws.py`, broadcast en pipeline |
| **TASK-028** | Gemini Context Cache (prompt caching) | `services/llm/prompt_cache.py`, ~75% ahorro tokens sistema |
| **TASK-029** | Dead Letter Queue para Celery | `tasks/dlq.py`, `tasks/base.py` (DLQTask), endpoints admin |
| **TASK-030** | Documentación API completa | 16 OpenAPI tags, Postman collection, webhooks.md |

---

## Componentes Completados

### Backend
- ✅ Multi-tenancy por broker (auth, leads, config, RAG, WebSocket)
- ✅ LLM multi-provider: Gemini → Claude → OpenAI (con router de failover automático)
- ✅ Caché semántico Redis (coseno, excluye PII)
- ✅ Gemini Context Cache para system prompts de broker
- ✅ MCP Server (herramientas de agendamiento vía Model Context Protocol)
- ✅ Sistema multi-agente: QualifierAgent, SchedulerAgent, FollowUpAgent, AgentSupervisor
- ✅ Circuit breakers (LLM, Calendar, Telegram)
- ✅ Dead Letter Queue para fallos de Celery
- ✅ Knowledge base RAG con pgvector
- ✅ WebSocket por broker para eventos en tiempo real
- ✅ Voz multi-provider: VAPI, Bland AI
- ✅ Google Calendar con Google Meet automático
- ✅ Campañas automatizadas con Celery
- ✅ Pipeline con auto-avance y broadcasts WebSocket
- ✅ Dashboard de costos LLM
- ✅ Versionado de prompts por broker
- ✅ Rate limiting por IP y endpoint

### Frontend
- ✅ Dashboard con métricas
- ✅ Kanban del pipeline (drag & drop)
- ✅ Interfaz de chat
- ✅ Gestión de leads, campañas, templates
- ✅ Configuración de broker (IA, voz, scoring)
- ✅ Gestión de usuarios y brokers (SUPERADMIN)
- ✅ Dashboard de costos LLM

### Testing
- ✅ Tests unitarios: agentes, voice providers, auth, chat
- ✅ Eval framework determinista (sin API key): DicomRuleMetric, TaskCompletionMetric
- ✅ Dataset de 51 conversaciones etiquetadas
- ✅ Baselines registrados (2026-02-22)

---

## Pendiente / Próximas Iteraciones

| Área | Descripción |
|------|-------------|
| CI/CD | Configurar GitHub Actions con PostgreSQL + Redis (TASK-019) |
| E2E Tests | Playwright para flujos críticos (register → lead → chat) |
| Multi-agente producción | Migración gradual con `MULTI_AGENT_ENABLED` por broker |
| RAG avanzado | Chunking semántico, re-ranking, fuentes múltiples |
| Scoring pipeline | Multiplicadores por etapa, triggers de reactivación |
| Audit logging | Modelo `AuditLog` para cambios críticos |
