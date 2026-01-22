from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import logging


from app.database import init_db, close_db
from app.config import settings
from app.routes import health, auth, leads, webhooks, telegram, chat, appointments, campaigns, pipeline, templates, voice, broker_config, broker_users, brokers
from app.celery_app import celery_app


# Configure logging
logging.basicConfig(level=logging.INFO)
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


# Create FastAPI app
app = FastAPI(
    title="AI Lead Agent Pro",
    description="Real estate lead management with AI",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False  # Disable automatic redirects to avoid CORS issues
)


# CORS middleware
# Get allowed origins from environment variable (comma-separated)
allowed_origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]
logger.info(f"CORS allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Trusted host middleware
allowed_hosts = ["localhost", "127.0.0.1"]
if settings.ENVIRONMENT == "production":
    allowed_hosts.append("*")  # Add production domain here

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts
)


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
    
    return {
        "status": "healthy" if db_status == "ok" and redis_status == "ok" else "degraded",
        "database": db_status,
        "redis": redis_status,
    }


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(leads.router, prefix="/api/v1/leads", tags=["leads"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(telegram.router, prefix="/api/v1/telegram", tags=["telegram"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(appointments.router, prefix="/api/v1/appointments", tags=["appointments"])
app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["campaigns"])
app.include_router(pipeline.router, prefix="/api/v1/pipeline", tags=["pipeline"])
app.include_router(templates.router, prefix="/api/v1/templates", tags=["templates"])
app.include_router(voice.router, prefix="/api/v1/calls", tags=["voice"])
app.include_router(broker_config.router, prefix="/api/broker", tags=["broker-config"])
app.include_router(broker_users.router, prefix="/api/broker", tags=["broker-users"])
app.include_router(brokers.router, prefix="/api/brokers", tags=["brokers"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

