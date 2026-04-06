"""
Observability health check endpoint — extends existing /health with Celery,
external API latencies, and per-component status.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.core.redis_client import get_redis
from app.models.user import User
from app.routes.observability.routes import _require_admin

logger = logging.getLogger(__name__)
health_router = APIRouter(prefix="/observability", tags=["observability"])


async def _ping_url(url: str, timeout: float = 3.0) -> Dict[str, Any]:
    """Ping an external URL and return latency."""
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            latency_ms = int((time.monotonic() - start) * 1000)
            return {"status": "ok", "latency_ms": latency_ms, "http_status": resp.status_code}
    except Exception as exc:
        return {"status": "error", "error": str(exc)[:100]}


@health_router.get("/health")
async def observability_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Extended health check: DB, Redis, Celery workers, and external API latencies.
    """
    _require_admin(current_user)

    checks: Dict[str, Any] = {}

    # --- PostgreSQL ---
    try:
        start = time.monotonic()
        await db.execute(__import__("sqlalchemy", fromlist=["text"]).text("SELECT 1"))
        checks["postgresql"] = {"status": "ok", "latency_ms": int((time.monotonic() - start) * 1000)}
    except Exception as exc:
        checks["postgresql"] = {"status": "error", "error": str(exc)[:100]}

    # --- Redis ---
    try:
        redis = await get_redis()
        start = time.monotonic()
        await redis.ping()
        checks["redis"] = {"status": "ok", "latency_ms": int((time.monotonic() - start) * 1000)}
    except Exception as exc:
        checks["redis"] = {"status": "error", "error": str(exc)[:100]}

    # --- Celery via Redis queue depth ---
    try:
        redis = await get_redis()
        celery_queue_len = await redis.llen("celery")
        checks["celery"] = {"status": "ok", "queue_depth": celery_queue_len}
    except Exception as exc:
        checks["celery"] = {"status": "error", "error": str(exc)[:100]}

    # --- External APIs (parallel pings) ---
    ext_pings = {
        "gemini": "https://generativelanguage.googleapis.com/",
        "telegram": "https://api.telegram.org/",
    }
    tasks = {name: asyncio.create_task(_ping_url(url)) for name, url in ext_pings.items()}
    for name, task in tasks.items():
        checks[f"ext_{name}"] = await task

    overall = "ok" if all(v.get("status") == "ok" for v in checks.values()) else "degraded"
    components = [
        {"name": name, **data}
        for name, data in checks.items()
    ]
    return {
        "status": overall,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "components": components,
    }
