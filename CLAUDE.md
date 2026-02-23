# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (from `backend/`)

```bash
# Activate virtualenv
source .venv/bin/activate

# Run dev server
uvicorn app.main:app --reload

# Run Celery worker
celery -A app.celery_app worker --loglevel=info

# Run Celery beat (periodic tasks)
celery -A app.celery_app beat --loglevel=info

# Run MCP server (standalone)
python -m app.mcp.server

# Run all tests (requires Docker services up)
.venv/bin/python -m pytest tests/ -v

# Run a specific test file (no DB required — skips integration conftest)
.venv/bin/python -m pytest tests/services/test_multi_agent.py -v --noconftest

# Run eval framework (deterministic metrics only, no LLM key needed)
.venv/bin/python -m pytest tests/evals/ -v --noconftest

# Run eval framework with LLM judge (requires OPENAI_API_KEY)
EVAL_LLM_ENABLED=true .venv/bin/python -m pytest tests/evals/ -v --noconftest

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Linting / formatting (not yet automated — project uses standard Python conventions)
```

### Frontend (from `frontend/`)

```bash
npm install
npm run dev       # dev server at http://localhost:5173
npm run build     # production build to dist/
```

### Docker (from project root)

```bash
docker-compose up -d                                    # start all services
docker-compose exec backend alembic upgrade head        # run migrations in container
```

---

## Architecture

### Overview

A multi-tenant real estate CRM where each **Broker** (real estate company) gets isolated leads, agents, and AI configuration. The AI agent **"Sofía"** qualifies leads and schedules property visits via chat (Telegram / WhatsApp) and voice calls (VAPI).

```
Frontend (React/Vite) ──HTTPS──► Backend (FastAPI)
                                       │
                        ┌──────────────┼──────────────┐
                        ▼              ▼               ▼
                   PostgreSQL       Redis           Celery Workers
                   (pgvector)    (cache/broker)   (campaigns, scoring)
                        │
                   External APIs: Gemini · Claude · OpenAI · VAPI · Telegram · Google Calendar
```

### Backend Structure (`backend/app/`)

The codebase uses a **dual-directory** pattern: most business domains live under `app/features/` (self-contained vertical slices), while older/shared code lives under `app/routes/` and `app/services/`.

**`app/features/`** — each subdirectory contains its own `routes.py` and is a full vertical slice:
- `auth/` — JWT registration/login
- `leads/` — lead CRUD
- `chat/` — inbound chat handling (delegates to `app/services/chat/orchestrator.py`)
- `broker/` — three route files: `routes_config.py`, `routes_users.py`, `routes_brokers.py`
- `appointments/`, `campaigns/`, `pipeline/`, `templates/`, `telegram/`, `voice/`, `webhooks/`

Most `app/features/X/routes.py` files are thin re-exports of the matching file in `app/routes/`.

**`app/routes/`** — actual implementation of several endpoints:
- `ws.py` — WebSocket endpoint (real-time events per broker)
- `knowledge_base.py` — RAG CRUD + semantic search
- `costs.py` — LLM cost analytics dashboard
- `admin_tasks.py` — DLQ management UI endpoints
- `health.py` — health check

**`app/services/`** — all business logic, organized by subdomain:

| Directory | Purpose |
|---|---|
| `llm/` | Provider abstraction layer (Gemini, Claude, OpenAI) |
| `agents/` | Multi-agent system (QualifierAgent → SchedulerAgent → FollowUpAgent) |
| `chat/` | Chat orchestrator, state machine, per-provider chat service |
| `pipeline/` | Stage advancement, metrics, constants |
| `leads/` | Lead context, scoring, service layer |
| `broker/` | Broker config service |
| `appointments/` | Appointment creation and Google Calendar integration |
| `campaigns/` | Campaign execution logic |
| `voice/` | VAPI voice call service |
| `llm/semantic_cache.py` | Redis-backed cosine-similarity cache (skips PII messages) |
| `llm/prompt_cache.py` | Gemini Context Cache for static broker system prompts |

### LLM Provider Layer (`app/services/llm/`)

All LLM calls go through `LLMServiceFacade` (static methods, never instantiate). The facade delegates to the provider selected by `LLM_PROVIDER` env var.

```
LLMServiceFacade          ← single entry point for all code
    └── get_llm_provider()
            └── LLMRouter (primary + fallback, auto-failover on transient errors)
                    ├── GeminiProvider
                    ├── ClaudeProvider
                    └── OpenAIProvider
```

Key methods on `LLMServiceFacade`:
- `analyze_lead_qualification(message, lead_context, ...)` — returns structured dict
- `generate_response_with_function_calling(system_prompt, contents, tools, ...)` — returns `(text, function_calls)`
- `build_llm_prompt(broker_id, lead_context, ...)` — assembles the full system prompt

`LLMMessage` (the unified message type) is defined in `base_provider.py`. When mocking LLM calls in tests, patch `app.services.llm.facade.LLMServiceFacade.<method>`.

### Multi-Agent System (`app/services/agents/`)

Specialist agents replace the monolithic chat orchestrator when `MULTI_AGENT_ENABLED=true`.

```
AgentSupervisor.process(message, AgentContext, db)
    ├── QualifierAgent   — stages: entrada, perfilamiento
    │       └── handoff to SchedulerAgent when all fields collected + DICOM clean
    ├── SchedulerAgent   — stage: calificacion_financiera
    │       └── handoff to FollowUpAgent on appointment confirmation
    └── FollowUpAgent    — stages: agendado, seguimiento, referidos
```

Routing priority (most specific first): FollowUp > Scheduler > Qualifier. `AgentContext` is an immutable snapshot; `HandoffSignal` carries context updates across agent boundaries.

### Pipeline Stages

Ordered stages for Chilean real estate leads:
```
entrada → perfilamiento → calificacion_financiera → agendado → seguimiento → referidos → ganado/perdido
```

Stage transitions trigger WebSocket broadcasts (`ws_manager.broadcast`) and activity log entries.

### Celery Tasks (`app/tasks/`)

All tasks use `DLQTask` as base class (defined in `tasks/base.py`). When `max_retries` is exhausted, the task is automatically pushed to the Dead Letter Queue (`tasks/dlq.py` — Redis-backed).

Key task files: `campaign_executor.py`, `scoring_tasks.py`, `telegram_tasks.py`, `voice_tasks.py`, `dlq_tasks.py` (DLQ retry/discard operations).

### WebSocket (`app/core/websocket_manager.py`)

Singleton `ws_manager` manages connections per `broker_id`. Frontend connects at `GET /ws/{broker_id}` (with JWT). Event types: `new_message`, `stage_changed`, `lead_assigned`, `lead_hot`, `typing`.

### MCP Server (`app/mcp/`)

Standalone FastMCP server exposing appointment-scheduling tools. Can run as a sidecar (`python -m app.mcp.server`) or be called in-process via `MCPClientAdapter`. Transport controlled by `MCP_TRANSPORT` (`http` or `stdio`).

### Data Model Key Points

- **Multi-tenancy**: every table with user data has a `broker_id` FK — always filter by it.
- `Lead.lead_metadata` (JSONB): stores everything not in a typed column — conversation state, pipeline metadata, scoring components.
- `BrokerPromptConfig`: per-broker AI persona, system prompt, few-shot examples, DICOM instructions.
- `KnowledgeBase`: pgvector table with 768-dim embeddings (Gemini `text-embedding-004`), searched via cosine similarity.

### Frontend (`frontend/src/`)

React 18 + Vite, state management with **Zustand** stores (`store/*.js`). Organized by feature under `features/`. API calls proxy through Vite's `/api` and `/auth` dev proxy to `localhost:8000`.

### Testing

- Integration tests (`tests/conftest.py`) require running PostgreSQL + Redis — they import the full app.
- Unit tests for agents / evals are self-contained: run with `--noconftest` to skip the DB-requiring conftest.
- Eval dataset at `tests/evals/dataset/conversations.json` (51 labeled conversations).
- DICOM rule metric and task-completion metric are deterministic (regex) and never call an LLM.
- Baseline scores recorded in `docs/testing/eval_baseline.md`.

### Critical Domain Rules

- **DICOM rule**: never promise credit pre-approval, financing, or "pre-aprobación" to a lead whose `dicom_status == "dirty"`. The `QualifierAgent` enforces this — no handoff is emitted when DICOM is dirty. The `DicomRuleMetric` in the eval suite validates this.
- Pipeline stages are defined in `app/services/pipeline/constants.py` (`PIPELINE_STAGES` dict) — do not hardcode stage strings elsewhere.
- `lead_metadata` is encrypted at rest for PII fields (see `app/core/encryption.py`).
