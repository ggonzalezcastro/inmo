"""
Dead Letter Queue (DLQ) manager for failed Celery tasks (TASK-029).

Storage layout in Redis
-----------------------
- Sorted set  ``celery:dlq:index``  (score = epoch timestamp) → member = entry_id
- String key  ``celery:dlq:entry:{id}``  → JSON blob with full task metadata

This allows:
  • O(log N) insert / delete (ZADD / ZREM)
  • Paginated listing newest-first (ZREVRANGE)
  • O(1) lookup by ID (GET)
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_INDEX_KEY = "celery:dlq:index"
_ENTRY_PREFIX = "celery:dlq:entry:"
_ENTRY_TTL = 30 * 24 * 3600  # keep for 30 days


def _get_redis():
    """Return a Redis client or None when unavailable."""
    try:
        from app.core.cache import _get_redis as _core_get_redis
        return _core_get_redis()
    except Exception:
        return None


class DLQManager:
    """Async CRUD for the Dead Letter Queue backed by Redis."""

    # ── Write ─────────────────────────────────────────────────────────────────

    @classmethod
    async def push(
        cls,
        *,
        task_name: str,
        args: List[Any],
        kwargs: Dict[str, Any],
        exception: str,
        traceback: str = "",
        retries: int = 0,
    ) -> str:
        """Push a failed task to the DLQ. Returns the entry ID."""
        entry_id = str(uuid.uuid4())
        entry = {
            "id": entry_id,
            "task_name": task_name,
            "args": args,
            "kwargs": kwargs,
            "exception": exception[:500],
            "traceback": traceback[:2000],
            "retries": retries,
            "failed_at": time.time(),
            "status": "failed",
        }
        client = _get_redis()
        if client:
            now = time.time()
            pipe = client.pipeline()
            pipe.zadd(_INDEX_KEY, {entry_id: now})
            pipe.setex(f"{_ENTRY_PREFIX}{entry_id}", _ENTRY_TTL, json.dumps(entry))
            await pipe.execute()
        logger.warning(
            "[DLQ] Task pushed: %s id=%s retries=%d exc=%s",
            task_name, entry_id, retries, exception[:120],
        )
        return entry_id

    # ── Read ──────────────────────────────────────────────────────────────────

    @classmethod
    async def count(cls) -> int:
        """Return number of tasks currently in the DLQ."""
        client = _get_redis()
        if not client:
            return 0
        try:
            return await client.zcard(_INDEX_KEY)
        except Exception:
            return 0

    @classmethod
    async def list_failed(cls, offset: int = 0, limit: int = 100) -> List[Dict]:
        """Return up to ``limit`` entries newest-first, skipping ``offset``."""
        client = _get_redis()
        if not client:
            return []
        try:
            # Newest-first via ZREVRANGE
            ids = await client.zrevrange(_INDEX_KEY, offset, offset + limit - 1)
            entries = []
            for eid in ids:
                raw = await client.get(f"{_ENTRY_PREFIX}{eid}")
                if raw:
                    try:
                        entries.append(json.loads(raw))
                    except json.JSONDecodeError:
                        pass
            return entries
        except Exception as exc:
            logger.debug("[DLQ] list_failed error: %s", exc)
            return []

    @classmethod
    async def get(cls, entry_id: str) -> Optional[Dict]:
        """Return a single DLQ entry by ID, or None if not found."""
        client = _get_redis()
        if not client:
            return None
        try:
            raw = await client.get(f"{_ENTRY_PREFIX}{entry_id}")
            return json.loads(raw) if raw else None
        except Exception:
            return None

    # ── Delete / retry ────────────────────────────────────────────────────────

    @classmethod
    async def delete(cls, entry_id: str) -> bool:
        """Remove an entry from DLQ without retrying. Returns True if found."""
        client = _get_redis()
        if not client:
            return False
        try:
            removed = await client.zrem(_INDEX_KEY, entry_id)
            await client.delete(f"{_ENTRY_PREFIX}{entry_id}")
            return bool(removed)
        except Exception as exc:
            logger.debug("[DLQ] delete error: %s", exc)
            return False

    @classmethod
    async def retry(cls, entry_id: str) -> bool:
        """
        Requeue a DLQ task via Celery, then remove it from the DLQ.

        Returns True if the entry was found and requeued.
        """
        entry = await cls.get(entry_id)
        if not entry:
            return False
        try:
            from app.celery_app import celery_app

            celery_app.send_task(
                entry["task_name"],
                args=entry.get("args", []),
                kwargs=entry.get("kwargs", {}),
            )
            await cls.delete(entry_id)
            logger.info("[DLQ] Retried task %s id=%s", entry["task_name"], entry_id)
            return True
        except Exception as exc:
            logger.error("[DLQ] retry failed for %s: %s", entry_id, exc)
            return False
