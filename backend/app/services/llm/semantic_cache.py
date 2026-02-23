"""
SemanticCache — Redis-backed semantic similarity cache for LLM responses.

Only non-PII messages (greetings, FAQ-style questions) are cached.
Similarity is computed via cosine distance on Gemini text embeddings.

Redis key structure (per broker):
    semcache:{broker_id}  →  JSON list[{embedding:[...], response:"..."}]

Hit/miss counters (global):
    semcache:hits   →  int
    semcache:misses →  int

Usage:
    cached = await SemanticCache.lookup(message, broker_id)
    if cached:
        return cached
    response = await llm.generate(...)
    await SemanticCache.store(message, response, broker_id)
"""
from __future__ import annotations

import logging
import re
from math import sqrt
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── PII patterns (messages matching ANY pattern are NOT cached) ────────────────

_PII_PATTERNS = [
    re.compile(r"\b\d{7,15}\b"),                            # phone / ID numbers
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # email
    re.compile(r"\b(dicom|morosidad|deuda|renta|sueldo|ingreso|salary)\b", re.I),
    re.compile(r"\$\s*\d+"),                                # price mentions
    re.compile(r"\b\d{1,3}[.,]\d{3}([.,]\d{3})?\b"),       # CLP amounts like 1.200.000
]


def _is_pii(message: str) -> bool:
    """Return True if the message likely contains personal or financial data."""
    for pattern in _PII_PATTERNS:
        if pattern.search(message):
            return True
    return False


# ── Cosine similarity (pure Python — no numpy required) ──────────────────────

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sqrt(sum(x * x for x in a))
    norm_b = sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── Embedding helper ──────────────────────────────────────────────────────────

async def _get_embedding(text: str) -> Optional[List[float]]:
    """Fetch text embedding from Gemini. Returns None on failure."""
    try:
        from google import genai
        from app.config import settings

        if not settings.GEMINI_API_KEY:
            return None

        import asyncio

        def _sync_embed():
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            result = client.models.embed_content(
                model="text-embedding-004",
                contents=text,
            )
            return list(result.embeddings[0].values)

        return await asyncio.to_thread(_sync_embed)
    except Exception as exc:
        logger.debug("Embedding request failed: %s", exc)
        return None


# ── Counter helpers ───────────────────────────────────────────────────────────

_HIT_KEY = "semcache:hits"
_MISS_KEY = "semcache:misses"


async def _incr(key: str) -> None:
    try:
        from app.core.cache import _get_redis

        client = _get_redis()
        if client:
            await client.incr(key)
    except Exception:
        pass


async def get_hit_rate() -> dict:
    """Return {hits, misses, hit_rate} for the /health endpoint."""
    try:
        from app.core.cache import _get_redis

        client = _get_redis()
        if not client:
            return {"hits": 0, "misses": 0, "hit_rate": 0.0}
        hits_raw, misses_raw = await client.mget(_HIT_KEY, _MISS_KEY)
        hits = int(hits_raw or 0)
        misses = int(misses_raw or 0)
        total = hits + misses
        hit_rate = round(hits / total, 3) if total > 0 else 0.0
        return {"hits": hits, "misses": misses, "hit_rate": hit_rate}
    except Exception:
        return {"hits": 0, "misses": 0, "hit_rate": 0.0}


# ── SemanticCache API ─────────────────────────────────────────────────────────

class SemanticCache:
    """Semantic similarity cache backed by Redis + Gemini embeddings."""

    CACHE_KEY_PREFIX = "semcache:"

    @classmethod
    async def lookup(cls, message: str, broker_id: int) -> Optional[str]:
        """
        Look up a semantically similar cached response.

        Returns the cached response string, or None if no match (or PII detected).
        """
        from app.config import settings

        if not settings.SEMANTIC_CACHE_ENABLED:
            return None

        if _is_pii(message):
            logger.debug("[SemanticCache] PII detected — skipping cache lookup")
            return None

        embedding = await _get_embedding(message)
        if embedding is None:
            await _incr(_MISS_KEY)
            return None

        from app.core.cache import cache_get_json

        redis_key = f"{cls.CACHE_KEY_PREFIX}{broker_id}"
        entries = await cache_get_json(redis_key)

        if not entries:
            await _incr(_MISS_KEY)
            return None

        threshold = settings.SEMANTIC_CACHE_THRESHOLD
        best_score = 0.0
        best_response: Optional[str] = None

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            cached_emb = entry.get("embedding")
            if isinstance(cached_emb, list) and cached_emb:
                score = _cosine_similarity(embedding, cached_emb)
                if score > best_score:
                    best_score = score
                    best_response = entry.get("response")

        if best_score >= threshold and best_response:
            await _incr(_HIT_KEY)
            logger.debug(
                "[SemanticCache] HIT broker_id=%s score=%.3f", broker_id, best_score
            )
            return best_response

        await _incr(_MISS_KEY)
        return None

    @classmethod
    async def store(cls, message: str, response: str, broker_id: int) -> None:
        """
        Store a (message, response) pair in the semantic cache.
        Skips PII messages silently.
        """
        from app.config import settings

        if not settings.SEMANTIC_CACHE_ENABLED:
            return

        if _is_pii(message):
            return

        embedding = await _get_embedding(message)
        if embedding is None:
            return

        from app.core.cache import cache_get_json, cache_set_json

        redis_key = f"{cls.CACHE_KEY_PREFIX}{broker_id}"
        entries: list = await cache_get_json(redis_key) or []

        max_entries = settings.SEMANTIC_CACHE_MAX_ENTRIES
        if len(entries) >= max_entries:
            entries = entries[-(max_entries - 1):]  # keep newest

        entries.append({"embedding": embedding, "response": response})
        await cache_set_json(redis_key, entries, ttl_seconds=settings.SEMANTIC_CACHE_TTL)
        logger.debug("[SemanticCache] Stored entry broker_id=%s total=%d", broker_id, len(entries))
