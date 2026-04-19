"""
Gemini Context Caching manager (TASK-028).

Caches the per-broker *static* system prompt using Gemini's Context Caching
API, reducing input-token costs by ~75% for the cached prefix.

Design
------
- One cache entry per (broker_id, prompt_hash) pair.
- The Gemini resource name is persisted in Redis (TTL = GEMINI_CONTEXT_CACHE_TTL).
- A new cache is created (or refreshed) when:
    • No Redis entry exists for this broker/hash
    • The existing entry will expire within 30 minutes
- All errors are caught and logged; None is returned so callers degrade
  gracefully to uncached generation.
- Disabled by default (GEMINI_CONTEXT_CACHING_ENABLED=false).
  Enable in production once the system prompt exceeds ~4 096 tokens (e.g.
  after adding RAG chunks — TASK-024).

Metrics
-------
In-process hit/miss counters are exposed via get_stats() and surfaced in
the /health endpoint.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Optional

from app.config import settings
from app.core.cache import cache_delete, cache_get_json, cache_set_json

logger = logging.getLogger(__name__)

_REDIS_KEY_PREFIX = "gemini_ctx_cache:"
# Refresh when < 30 min of TTL remaining on the Gemini-side cache
_REFRESH_THRESHOLD_S = 1800

# In-process counters (reset on restart; good enough for /health dashboards)
_hits: dict[int, int] = {}
_misses: dict[int, int] = {}


class PromptCacheManager:
    """Manages Gemini Context Cache entries per broker."""

    # ── Public async API ─────────────────────────────────────────────────────

    @classmethod
    async def get_cache_name(
        cls,
        *,
        broker_id: int,
        system_prompt: str,
        gemini_client,
        model: str,
    ) -> Optional[str]:
        """
        Return the Gemini cache resource name for this broker's prompt.

        Creates or refreshes the Gemini-side cache as needed. Returns None
        when caching is disabled or any error occurs.
        """
        if not settings.GEMINI_CONTEXT_CACHING_ENABLED:
            return None

        ttl = settings.GEMINI_CONTEXT_CACHE_TTL
        prompt_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:16]
        redis_key = f"{_REDIS_KEY_PREFIX}{broker_id}:{prompt_hash}"

        # 1. Redis hit — reuse existing cache if not near expiry
        entry = await cache_get_json(redis_key)
        if entry and entry.get("cache_name"):
            remaining = entry.get("remaining_ttl", 0)
            if remaining > _REFRESH_THRESHOLD_S:
                _hits[broker_id] = _hits.get(broker_id, 0) + 1
                logger.debug("[PromptCache] HIT broker=%s cache=%s", broker_id, entry["cache_name"])
                return entry["cache_name"]

        # 2. Miss / near-expiry — create (or refresh) on Gemini
        _misses[broker_id] = _misses.get(broker_id, 0) + 1
        try:
            cache_name = await asyncio.to_thread(
                cls._create_cache, gemini_client, model, system_prompt, broker_id, ttl
            )
        except Exception as exc:
            logger.warning("[PromptCache] Cache creation failed broker=%s: %s", broker_id, exc)
            return None

        if cache_name:
            # Store in Redis, expiring 2 min before the Gemini-side TTL
            await cache_set_json(
                redis_key,
                {"cache_name": cache_name, "remaining_ttl": ttl},
                ttl_seconds=max(ttl - 120, 60),
            )
            logger.info("[PromptCache] Created cache broker=%s name=%s", broker_id, cache_name)

        return cache_name

    @classmethod
    async def invalidate(cls, broker_id: int, system_prompt: str) -> None:
        """Remove Redis entry for a broker (call when system prompt changes)."""
        prompt_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:16]
        redis_key = f"{_REDIS_KEY_PREFIX}{broker_id}:{prompt_hash}"
        await cache_delete(redis_key)
        logger.info("[PromptCache] Invalidated Redis entry broker=%s", broker_id)

    @classmethod
    def get_stats(cls) -> dict:
        """Return aggregate hit/miss stats (for /health endpoint)."""
        total_hits = sum(_hits.values())
        total_misses = sum(_misses.values())
        total = total_hits + total_misses
        return {
            "enabled": settings.GEMINI_CONTEXT_CACHING_ENABLED,
            "hits": total_hits,
            "misses": total_misses,
            "hit_rate": round(total_hits / total, 3) if total else 0.0,
        }

    # ── Private sync helper (runs in thread) ─────────────────────────────────

    @staticmethod
    def _create_cache(
        client,
        model: str,
        system_prompt: str,
        broker_id: int,
        ttl_seconds: int,
    ) -> Optional[str]:
        """Synchronous: create the Gemini cached content resource."""
        try:
            from google.genai import types as genai_types

            cache = client.caches.create(
                model=model,
                config=genai_types.CreateCachedContentConfig(
                    display_name=f"broker-{broker_id}-system-prompt",
                    system_instruction=system_prompt,
                    ttl=f"{ttl_seconds}s",
                ),
            )
            return cache.name
        except Exception as exc:
            logger.warning("[PromptCache] Gemini caches.create error: %s", exc)
            return None
