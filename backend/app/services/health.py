"""
Shared health check logic used by /health and /api/v1/admin/health endpoints.
"""
from __future__ import annotations


async def get_system_health() -> dict:
    """
    Returns a dict with the full system health snapshot:
    - database, redis, circuit_breakers, semantic_cache, prompt_cache, websocket
    """
    from app.database import engine
    from sqlalchemy import text
    from redis import Redis
    from app.config import settings

    # Database
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.scalar()
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Redis
    try:
        r = Redis.from_url(settings.REDIS_URL)
        r.ping()
        redis_status = "ok"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    # Circuit breakers
    from app.core.circuit_breakers import get_breaker_states
    breaker_states = get_breaker_states()
    any_open = any(s == "open" for s in breaker_states.values())

    # Semantic cache
    from app.services.llm.semantic_cache import get_hit_rate
    semantic_cache_stats = await get_hit_rate()

    # Gemini context cache
    from app.services.llm.prompt_cache import PromptCacheManager
    prompt_cache_stats = PromptCacheManager.get_stats()

    # WebSocket connections
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
