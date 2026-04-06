"""
Async Redis client helper.

Provides a single shared `redis.asyncio.Redis` instance for pub/sub and
general-purpose async Redis operations. Mirrors the connection pattern
used by WebSocketManager.
"""
from __future__ import annotations

from functools import lru_cache
import redis.asyncio as aioredis

from app.core.config import settings


@lru_cache(maxsize=1)
def _get_async_redis() -> aioredis.Redis:
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_redis() -> aioredis.Redis:
    """Return the shared async Redis client."""
    return _get_async_redis()
