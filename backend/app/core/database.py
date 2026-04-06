from typing import AsyncGenerator
from sqlalchemy import text, create_engine
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.models.base import Base


# Build engine arguments based on environment
engine_args = {
    "echo": settings.DEBUG,
    "future": True,
    "pool_pre_ping": True,  # Verify connections before using
}

if settings.ENVIRONMENT == "test":
    engine_args["poolclass"] = NullPool
else:
    engine_args["pool_size"] = settings.DB_POOL_SIZE
    engine_args["max_overflow"] = settings.DB_MAX_OVERFLOW

# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    **engine_args
)


# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# Dependency for FastAPI routes
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for FastAPI dependency injection"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Initialize database
async def init_db():
    """Create all tables. Ensures pgvector extension exists for knowledge_base."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections"""
    await engine.dispose()


# ── Sync engine for Celery workers ──────────────────────────────────────────
# Celery tasks run in a synchronous context; replace asyncpg driver with psycopg2.
_sync_url = settings.DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
).replace("postgresql+aiopg://", "postgresql+psycopg2://")

_sync_engine = create_engine(
    _sync_url,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SyncSessionLocal: sessionmaker[Session] = sessionmaker(
    bind=_sync_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
