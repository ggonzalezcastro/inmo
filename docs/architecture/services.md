# Services & Modules

## Backend Module Map

```
backend/app/
├── main.py                  # FastAPI app factory, middleware, router registration
├── config.py                # Settings (pydantic-settings, .env)
├── database.py              # Async SQLAlchemy engine, session factory
├── celery_app.py            # Celery app instance
├── core/
│   ├── cache.py             # Redis helpers (get/set/delete)
│   ├── circuit_breakers.py  # pybreaker instances per LLM provider
│   ├── encryption.py        # Field-level encryption utilities
│   ├── logging_config.py    # Structured JSON logging setup
│   ├── telemetry.py         # OpenTelemetry / Jaeger setup
│   └── websocket_manager.py # In-memory WS connection registry
├── middleware/
│   ├── auth.py              # JWT creation, decoding, get_current_user dep
│   ├── permissions.py       # Permissions.require_admin, require_superadmin
│   └── rate_limiter.py      # Redis-backed rate limiter (production)
├── models/                  # SQLAlchemy ORM models (see database.md)
├── schemas/                 # Pydantic request/response schemas
├── routes/                  # Actual router implementations
│   ├── auth.py              # /auth/*
│   ├── leads.py             # /api/v1/leads/*
│   ├── chat.py              # /api/v1/chat/*
│   ├── appointments.py      # /api/v1/appointments/*
│   ├── campaigns.py         # /api/v1/campaigns/*
│   ├── pipeline.py          # /api/v1/pipeline/*
│   ├── templates.py         # /api/v1/templates/*
│   ├── voice.py             # /api/v1/calls/*
│   ├── broker_config.py     # /api/broker/*
│   ├── broker_users.py      # /api/broker/users/*
│   ├── brokers.py           # /api/brokers/*
│   ├── costs.py             # /api/v1/admin/costs/*
│   ├── admin_tasks.py       # /api/v1/admin/tasks/*
│   ├── ws.py                # /ws/{broker_id}/{user_id}
│   └── knowledge_base.py    # /api/v1/kb/*
├── features/                # Feature modules (re-export routes from routes/)
│   ├── auth/routes.py
│   ├── leads/routes.py
│   ├── chat/routes.py
│   ├── appointments/routes.py
│   ├── campaigns/routes.py
│   ├── pipeline/routes.py
│   ├── templates/routes.py
│   ├── voice/routes.py
│   ├── webhooks/routes.py
│   ├── telegram/routes.py
│   ├── whatsapp/routes.py
│   └── broker/
│       ├── routes_config.py
│       ├── routes_users.py
│       └── routes_brokers.py
└── services/
    ├── leads.py             # LeadService, ScoringService
    ├── pipeline.py          # PipelineService, stage transitions
    ├── chat.py              # ChatOrchestratorService
    ├── shared.py            # ActivityService
    ├── broker.py            # BrokerInitService
    ├── llm/
    │   ├── factory.py       # get_llm_provider()
    │   ├── semantic_cache.py
    │   └── prompt_cache.py  # Gemini context caching (TASK-028)
    ├── agents/              # MCP-based tool agents
    ├── appointments/
    ├── campaigns/
    └── voice/
```

## Key Services

### `ChatOrchestratorService`
Central orchestrator for all incoming messages. Steps:
1. Resolve or create `Lead` from channel user ID.
2. Load lead context (`LeadContextService`).
3. Check semantic cache — return cached response if hit ≥ 0.92 similarity.
4. Build system prompt from `BrokerPromptConfig` + RAG KB results.
5. Call LLM via `LLMServiceFacade` (with circuit breaker + fallback).
6. Parse LLM response for extracted fields (name, budget, location, DICOM status).
7. Recalculate `lead_score` via `ScoringService`.
8. Advance `pipeline_stage` via `PipelineService`.
9. Persist `ChatMessage`, update `Lead`, log `LLMCall`.
10. Broadcast WebSocket events to connected dashboard clients.

### `ScoringService`
Calculates `lead_score` (0–100) from weighted components:
- **base**: field completeness (name, phone, email, location, budget) — weights from `BrokerLeadConfig.field_weights`
- **behavior**: message engagement, response rate
- **engagement**: conversation depth, appointment acceptance
- **stage**: current pipeline stage bonus
- **financial**: income range, DICOM status
- **penalties**: inactivity, negative signals

Thresholds (configurable per broker in `BrokerLeadConfig`):
- `cold_max_score` default 20
- `warm_max_score` default 50
- `hot_min_score` default 50
- `qualified_min_score` default 75

### `PipelineService`
Manages stage transitions. Calls `calcular_calificacion()` to set `lead_metadata.calificacion` (`calificado` / `potencial` / `no_calificado`) and `actualizar_pipeline_stage()` to advance the lead through the funnel.

### `BrokerInitService`
Called at registration. Creates `Broker`, `BrokerPromptConfig`, `BrokerLeadConfig`, `BrokerVoiceConfig`, `BrokerChatConfig` with sensible defaults and promotes the registering user from `AGENT` → `ADMIN`.

### `LLMServiceFacade`
Abstracts provider selection. Uses `LLM_TEMPERATURE_QUALIFY=0.3`, `LLM_TEMPERATURE_CHAT=0.7`, `LLM_TEMPERATURE_JSON=0.1` per call type. Routes through circuit breakers; on open circuit falls back to `LLM_FALLBACK_PROVIDER`.
