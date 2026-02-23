import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
import logging

from app.core.logging_config import setup_logging
from app.core.telemetry import setup_tracing
from app.database import init_db, close_db
from app.config import settings

# ── Logging must be configured before any other module logs anything ──────────
setup_logging(
    environment=settings.ENVIRONMENT,
    log_level="DEBUG" if settings.DEBUG else "INFO",
)
from app.features.auth.routes import router as auth_router
from app.features.leads.routes import router as leads_router
from app.features.webhooks.routes import router as webhooks_router
from app.features.telegram.routes import router as telegram_router
from app.features.chat.routes import router as chat_router
from app.features.appointments.routes import router as appointments_router
from app.features.campaigns.routes import router as campaigns_router
from app.features.pipeline.routes import router as pipeline_router
from app.features.templates.routes import router as templates_router
from app.features.voice.routes import router as voice_router
from app.features.broker.routes_config import router as broker_config_router
from app.features.broker.routes_users import router as broker_users_router
from app.features.broker.routes_brokers import router as brokers_router
from app.routes.costs import router as costs_router
from app.routes.admin_tasks import router as admin_tasks_router
from app.routes.ws import router as ws_router
from app.routes.knowledge_base import router as kb_router
from app.celery_app import celery_app


logger = logging.getLogger(__name__)


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up application...")
    await init_db()
    yield
    # Shutdown
    logger.info("Shutting down application...")
    await close_db()


# ── OpenAPI tag descriptions ──────────────────────────────────────────────────
_TAGS_METADATA = [
    {
        "name": "auth",
        "description": "Authentication endpoints. Register a new broker, log in and obtain a JWT "
                       "Bearer token, or inspect the current user profile.",
    },
    {
        "name": "leads",
        "description": "Full CRUD for real-estate leads with role-based filtering, CSV bulk import, "
                       "pipeline stage management, lead-score recalculation, and agent assignment.",
    },
    {
        "name": "chat",
        "description": "AI conversation endpoints powered by Sofía (Gemini/Claude). "
                       "Send a message from a lead and receive an AI-generated response with live "
                       "lead-score updates. Supports SSE streaming (`/stream`).",
    },
    {
        "name": "appointments",
        "description": "Schedule, confirm, and cancel property-visit appointments. "
                       "Integrates with Google Calendar when configured.",
    },
    {
        "name": "campaigns",
        "description": "Multi-step drip campaigns (WhatsApp / Telegram / email). "
                       "Create campaigns, add steps, apply to leads, and track execution logs.",
    },
    {
        "name": "pipeline",
        "description": "Pipeline stage management and conversion metrics. "
                       "Move leads between stages, auto-advance based on conditions, and view funnel KPIs.",
    },
    {
        "name": "templates",
        "description": "Message templates for campaigns and manual outreach. "
                       "Supports variable interpolation ({{name}}, {{broker_name}}, etc.).",
    },
    {
        "name": "voice",
        "description": "Outbound AI voice calls via VAPI (or compatible provider). "
                       "Initiate calls, receive provider webhooks, and retrieve call transcripts.",
    },
    {
        "name": "webhooks",
        "description": "Inbound webhook receivers for Telegram and WhatsApp. "
                       "These endpoints are called directly by the messaging providers.",
    },
    {
        "name": "broker-config",
        "description": "Broker-specific configuration: system prompt versions, lead-scoring weights, "
                       "and prompt preview.",
    },
    {
        "name": "broker-users",
        "description": "User management scoped to a broker (ADMIN/SUPERADMIN only). "
                       "Create, update, and deactivate users.",
    },
    {
        "name": "brokers",
        "description": "Broker CRUD (SUPERADMIN only). Create and manage broker organisations.",
    },
    {
        "name": "costs",
        "description": "LLM cost analytics: per-broker summary, daily chart data, outlier detection, "
                       "CSV export, and cross-broker aggregation (SUPERADMIN).",
    },
    {
        "name": "admin-tasks",
        "description": "Dead Letter Queue (DLQ) management for failed Celery tasks. "
                       "List, retry, or discard failed background jobs.",
    },
    {
        "name": "websocket",
        "description": "WebSocket endpoint for real-time CRM updates (new messages, "
                       "pipeline stage changes, lead-assigned events). "
                       "Authenticate by sending `{\"token\": \"<jwt>\"}` as the first frame.",
    },
    {
        "name": "knowledge-base",
        "description": "RAG knowledge base backed by pgvector. "
                       "Manage documents (auto-embedded with Gemini text-embedding-004) "
                       "and run semantic search.",
    },
]

# Create FastAPI app
app = FastAPI(
    title="AI Lead Agent Pro",
    description=(
        "## Real estate lead management powered by AI\n\n"
        "Sofía is an AI qualification agent that manages incoming real estate leads via "
        "WhatsApp, Telegram, and web chat. This API exposes all CRM operations, "
        "AI conversation endpoints, and administrative utilities.\n\n"
        "### Authentication\n"
        "All endpoints (except `/auth/register`, `/auth/login`, and webhooks) require a "
        "**Bearer token** in the `Authorization` header.\n\n"
        "```\nAuthorization: Bearer <access_token>\n```\n\n"
        "### Roles\n"
        "| Role | Capabilities |\n"
        "|------|--------------|\n"
        "| `AGENT` | Read own leads, send messages |\n"
        "| `ADMIN` | Full broker scope |\n"
        "| `SUPERADMIN` | All brokers, cost analytics, broker management |\n"
    ),
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,
    openapi_tags=_TAGS_METADATA,
    contact={
        "name": "AI Lead Agent Pro Support",
        "url": "https://github.com/your-org/inmo",
    },
    license_info={
        "name": "Proprietary",
    },
)

# ── OpenTelemetry tracing (no-op when OTEL_ENABLED != true) ──────────────────
setup_tracing(app)


# ── Request-ID middleware ─────────────────────────────────────────────────────
class RequestIDMiddleware(BaseHTTPMiddleware):
    """Injects a unique request_id into every request and response header."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestIDMiddleware)


# Global exception handler - prevents exposing internal error details
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch unhandled exceptions and return safe error response.
    In production, don't expose internal error details.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    if settings.ENVIRONMENT == "production":
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal error occurred. Please try again later."}
        )
    else:
        # In development, show more details for debugging
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__}
        )


# HTTPS redirect middleware (production only)
if settings.ENVIRONMENT == "production" and getattr(settings, 'FORCE_HTTPS', False):
    app.add_middleware(HTTPSRedirectMiddleware)
    logger.info("HTTPS redirect middleware enabled")


# CORS middleware with stricter settings for production
allowed_origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]
logger.info(f"CORS allowed origins: {allowed_origins}")

# Define allowed methods and headers based on environment
if settings.ENVIRONMENT == "production":
    # Production: restrict to only necessary methods and headers
    allowed_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allowed_headers = [
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
    ]
else:
    # Development: allow all for easier debugging
    allowed_methods = ["*"]
    allowed_headers = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=allowed_methods,
    allow_headers=allowed_headers,
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)


# Trusted host middleware
allowed_hosts = ["localhost", "127.0.0.1"]
if settings.ENVIRONMENT == "production":
    # In production, add your actual domain(s) here
    production_hosts = getattr(settings, 'ALLOWED_HOSTS', '').split(',')
    allowed_hosts.extend([h.strip() for h in production_hosts if h.strip()])

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts if settings.ENVIRONMENT == "production" else ["*"]
)


# Rate limiting middleware (production only)
if settings.ENVIRONMENT == "production":
    from app.middleware.rate_limiter import RateLimitMiddleware, get_rate_limiter
    rate_limiter = get_rate_limiter()
    app.add_middleware(
        RateLimitMiddleware,
        rate_limiter=rate_limiter,
        exclude_paths=["/health", "/docs", "/redoc", "/openapi.json", "/"]
    )
    logger.info("Rate limiting middleware enabled")


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "AI Lead Agent Pro API",
        "version": "1.0.0",
        "docs": "/docs"
    }


# Health check
@app.get("/health")
async def health_check():
    from app.database import engine
    from sqlalchemy import text
    from redis import Redis
    
    # Check database
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    # Check Redis
    try:
        r = Redis.from_url(settings.REDIS_URL)
        r.ping()
        redis_status = "ok"
    except Exception as e:
        redis_status = f"error: {str(e)}"
    
    # Circuit breaker states
    from app.core.circuit_breakers import get_breaker_states
    breaker_states = get_breaker_states()
    any_open = any(s == "open" for s in breaker_states.values())

    # Semantic cache hit rate
    from app.services.llm.semantic_cache import get_hit_rate
    semantic_cache_stats = await get_hit_rate()

    # Gemini context cache stats (TASK-028)
    from app.services.llm.prompt_cache import PromptCacheManager
    prompt_cache_stats = PromptCacheManager.get_stats()

    # WebSocket connection stats (TASK-027)
    from app.core.websocket_manager import ws_manager
    ws_stats = ws_manager.stats()

    overall = (
        "healthy"
        if db_status == "ok" and redis_status == "ok" and not any_open
        else "degraded"
    )

    return {
        "status": overall,
        "database": db_status,
        "redis": redis_status,
        "circuit_breakers": breaker_states,
        "semantic_cache": semantic_cache_stats,
        "prompt_cache": prompt_cache_stats,
        "websocket": ws_stats,
    }


# Include routers (from app.features)
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(leads_router, prefix="/api/v1/leads", tags=["leads"])
app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
app.include_router(telegram_router, prefix="/api/v1/telegram", tags=["telegram"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(appointments_router, prefix="/api/v1/appointments", tags=["appointments"])
app.include_router(campaigns_router, prefix="/api/v1/campaigns", tags=["campaigns"])
app.include_router(pipeline_router, prefix="/api/v1/pipeline", tags=["pipeline"])
app.include_router(templates_router, prefix="/api/v1/templates", tags=["templates"])
app.include_router(voice_router, prefix="/api/v1/calls", tags=["voice"])
app.include_router(broker_config_router, prefix="/api/broker", tags=["broker-config"])
app.include_router(broker_users_router, prefix="/api/broker", tags=["broker-users"])
app.include_router(brokers_router, prefix="/api/brokers", tags=["brokers"])
app.include_router(costs_router, prefix="/api/v1/admin/costs", tags=["costs"])
app.include_router(admin_tasks_router, prefix="/api/v1/admin/tasks", tags=["admin-tasks"])
app.include_router(ws_router, prefix="/ws", tags=["websocket"])
app.include_router(kb_router, prefix="/api/v1/kb", tags=["knowledge-base"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

