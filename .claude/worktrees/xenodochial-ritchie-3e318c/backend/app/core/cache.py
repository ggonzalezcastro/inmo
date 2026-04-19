"""
Redis cache helper for hot-path data (broker config, lead context).
Graceful fallback when Redis is unavailable.
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_redis_client = None


def _get_redis():
    """Lazy init Redis client (async). Returns None if Redis unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        from redis.asyncio import Redis
        from app.core.config import settings
        url = getattr(settings, "REDIS_URL", "") or ""
        if not url:
            return None
        _redis_client = Redis.from_url(url, decode_responses=True)
        return _redis_client
    except Exception as e:
        logger.warning("Redis cache not available: %s", e)
        return None


async def cache_get(key: str) -> Optional[str]:
    """Get value from cache. Returns None if miss or Redis unavailable."""
    try:
        client = _get_redis()
        if not client:
            return None
        return await client.get(key)
    except Exception as e:
        logger.debug("Cache get failed for %s: %s", key, e)
        return None


async def cache_set(key: str, value: str, ttl_seconds: int = 3600) -> bool:
    """Set value in cache with TTL. Returns False if Redis unavailable."""
    try:
        client = _get_redis()
        if not client:
            return False
        await client.setex(key, ttl_seconds, value)
        return True
    except Exception as e:
        logger.debug("Cache set failed for %s: %s", key, e)
        return False


async def cache_delete(key: str) -> bool:
    """Delete key from cache. Returns False if Redis unavailable."""
    try:
        client = _get_redis()
        if not client:
            return False
        await client.delete(key)
        return True
    except Exception as e:
        logger.debug("Cache delete failed for %s: %s", key, e)
        return False


async def cache_get_json(key: str) -> Optional[Any]:
    """Get JSON value from cache. Returns None if miss or error."""
    raw = await cache_get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def cache_set_json(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    """Set JSON-serializable value in cache."""
    try:
        return await cache_set(key, json.dumps(value, default=str), ttl_seconds)
    except (TypeError, ValueError):
        return False
