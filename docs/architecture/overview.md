---
title: Arquitectura General
version: 1.1.0
date: 2026-02-22
author: Equipo Inmo
---

# Arquitectura General

## Visión General

AI Lead Agent Pro es un CRM inmobiliario multi-tenant con IA integrada. La arquitectura se basa en capas con separación clara entre rutas, servicios y modelos, usando patrones de diseño como Strategy, Factory y Facade.

## Componentes Principales

### Backend (FastAPI)

El backend es una aplicación FastAPI completamente asíncrona:

| Capa | Directorio | Responsabilidad |
|------|-----------|-----------------|
| Routes | `app/routes/` | Endpoints HTTP, validación de entrada, serialización |
| Services | `app/services/` | Lógica de negocio organizada por dominio |
| Models | `app/models/` | Modelos SQLAlchemy (ORM) |
| Schemas | `app/schemas/` | Pydantic schemas para request/response |
| Tasks | `app/tasks/` | Tareas asíncronas Celery |
| Middleware | `app/middleware/` | Auth JWT, rate limiting, permisos |
| Core | `app/core/` | Configuración, base de datos, cache |

### Frontend (React 18 + TypeScript + Vite)

SPA con TypeScript strict mode, Shadcn/ui y Zustand para estado global.

**Stack**: React 18 · TypeScript · Vite · Tailwind CSS · Shadcn/ui (Radix UI) · Zustand · React Router v6 · @tanstack/react-table · sonner · lucide-react

**Arquitectura de directorios**:
```
src/
├── app/          # Router, App root (entry point)
├── features/     # Vertical slices por dominio
│   ├── auth/     # Login, Register, authStore, guards
│   ├── dashboard/
│   ├── leads/
│   ├── pipeline/
│   ├── campaigns/
│   ├── appointments/
│   ├── templates/
│   ├── settings/
│   ├── users/
│   ├── brokers/
│   ├── chat/     # Wrapper de ChatTest.jsx (sin modificar)
│   └── llm-costs/
└── shared/       # UI components, hooks, guards, lib
```

**Módulos y rutas**:

| Módulo | Ruta | Roles | Descripción |
|--------|------|-------|-------------|
| Dashboard | `/dashboard` | todos | KPIs, pipeline summary, leads calientes |
| Leads | `/leads` | todos | Tabla filtrable, detalle lateral, importación CSV |
| Pipeline | `/pipeline` | todos | Kanban de 8 etapas, actualizaciones optimistas |
| Campañas | `/campaigns` | admin, superadmin | CRUD de campañas y pasos |
| Citas | `/appointments` | todos | Agenda, confirmar/cancelar |
| Templates | `/templates` | admin, superadmin | Editor de plantillas con variables |
| Chat IA | `/chat` | todos | ChatTest.jsx (inalterado) |
| Costos LLM | `/costs` | admin, superadmin | Dashboard de costos por proveedor/broker |
| Configuración | `/settings` | admin, superadmin | Prompt IA, scoring, preview |
| Usuarios | `/users` | admin, superadmin | CRUD de usuarios del broker |
| Brokers | `/brokers` | superadmin | Gestión global de brokers |

### Infraestructura

| Servicio | Tecnología | Puerto |
|----------|-----------|--------|
| API Server | FastAPI + Uvicorn | 8000 |
| Database | PostgreSQL 15 | 5432 |
| Cache/Queue Broker | Redis | 6379 |
| Worker | Celery | N/A |
| Scheduler | Celery Beat | N/A |

## Multi-Tenancy

El sistema implementa multi-tenancy a nivel de base de datos:

- Cada **Broker** es una inmobiliaria independiente
- Los **Users** pertenecen a un broker
- Los **Leads** están vinculados a un broker
- Las configuraciones (prompts, scoring, voz, chat) son por broker
- Roles: `SUPERADMIN` (acceso global), `ADMIN` (broker), `AGENT` (leads asignados)

## Patrones de Diseño

### Strategy Pattern (Proveedores)

Tres dominios usan el patrón Strategy con factory:

1. **LLM**: `BaseLLMProvider` → `GeminiProvider`, `ClaudeProvider`, `OpenAIProvider`
2. **Voice**: `BaseVoiceProvider` → `VapiProvider`, `BlandProvider`
3. **Chat**: `BaseChatProvider` → `TelegramProvider`, `WhatsAppProvider`

### Multi-Agent System (Sprint 3)

Cuando `MULTI_AGENT_ENABLED=true`, el `ChatOrchestratorService` monolítico es reemplazado por agentes especializados:

```
AgentSupervisor
├── QualifierAgent   (entrada → perfilamiento)
├── SchedulerAgent   (calificacion_financiera)
└── FollowUpAgent    (agendado → seguimiento → referidos)
```

Los handoffs entre agentes se coordinan mediante `HandoffSignal`. Ver `docs/architecture/multi_agent.md` para detalles completos.

### Service Layer

Cada dominio tiene su propio subpaquete dentro de `services/`:

```
services/
├── agents/         # Sistema multi-agente (Qualifier, Scheduler, FollowUp, Supervisor)
├── voice/          # Llamadas de voz
├── llm/            # Modelos de lenguaje (facade, providers, router, cache)
├── chat/           # Mensajería multicanal
├── broker/         # Configuración de brokers
├── leads/          # Gestión de leads
├── pipeline/       # Pipeline de ventas
├── appointments/   # Citas y calendario
├── campaigns/      # Campañas automatizadas
├── knowledge/      # RAG — embeddings y búsqueda semántica
└── shared/         # Servicios transversales
```

### Caching

Redis se usa para:
- Contexto de leads (TTL 30 min)
- Configuración de prompts de broker (TTL 1 hora)
- Caché semántico de respuestas LLM por broker (coseno, excluye PII) — `llm/semantic_cache.py`
- Caché de contexto de Gemini para system prompts estáticos (~75% ahorro en tokens) — `llm/prompt_cache.py`
- Dead Letter Queue de tareas Celery — `tasks/dlq.py`
- Rate limiting (sliding window)
- Cola de tareas Celery

### WebSocket

`app/core/websocket_manager.py` mantiene conexiones activas por `broker_id`. El frontend se conecta a `GET /ws/{broker_id}` con JWT. Los cambios de etapa en pipeline, nuevos mensajes y actualizaciones de score se emiten en tiempo real.

## Flujo de Datos Principal

1. **Mensaje entrante** → Webhook → ChatOrchestratorService (o AgentSupervisor si `MULTI_AGENT_ENABLED`)
2. **Resolución de lead** → LeadService (crear o encontrar)
3. **Contexto** → LeadContextService (desde Redis o BD)
4. **Caché semántico** → SemanticCache.lookup() (evita llamada LLM si hay hit)
5. **Análisis LLM** → LLMServiceFacade → LLMRouter → Provider activo (Gemini/Claude/OpenAI)
6. **Scoring** → ScoringService (base + comportamiento + engagement + financiero)
7. **Pipeline** → PipelineService (auto-avance de etapa + broadcast WebSocket)
8. **Respuesta** → LLM genera respuesta → envía por canal
9. **Persistencia** → ChatService + ActivityService
