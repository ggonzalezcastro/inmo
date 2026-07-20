"""Manages active Pipecat pipeline tasks keyed by voice_call_id."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PipelineManager:
    """
    In-process registry of running Pipecat pipeline tasks.

    Each voice call runs as a separate asyncio Task. The manager tracks
    active tasks and exposes controls (stop, mute_tts, unmute_tts).
    For multi-worker deployments, extend with Redis-backed state.
    """

    def __init__(self) -> None:
        self._tasks: Dict[int, asyncio.Task] = {}
        self._tts_muted: Dict[int, bool] = {}
        self._cleaned_up: set[int] = set()

    def register(self, voice_call_id: int, task: asyncio.Task) -> None:
        self._tasks[voice_call_id] = task
        self._tts_muted[voice_call_id] = False
        self._cleaned_up.discard(voice_call_id)
        task.add_done_callback(lambda _: self._cleanup(voice_call_id))
        logger.info("[PipelineManager] registered call_id=%s", voice_call_id)

    async def stop(self, voice_call_id: int) -> bool:
        task = self._tasks.get(voice_call_id)
        if not task:
            return False
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=5.0)
        except asyncio.TimeoutError:
            pass
        # _cleanup is already triggered by done_callback, but ensure it ran
        self._cleanup(voice_call_id)
        logger.info("[PipelineManager] stopped call_id=%s", voice_call_id)
        return True

    def mute_tts(self, voice_call_id: int) -> bool:
        if voice_call_id not in self._tasks:
            logger.warning("[PipelineManager] mute_tts: call_id=%s not found", voice_call_id)
            return False
        self._tts_muted[voice_call_id] = True
        logger.info("[PipelineManager] TTS muted call_id=%s", voice_call_id)
        return True

    def unmute_tts(self, voice_call_id: int) -> bool:
        if voice_call_id not in self._tasks:
            logger.warning("[PipelineManager] unmute_tts: call_id=%s not found", voice_call_id)
            return False
        self._tts_muted[voice_call_id] = False
        logger.info("[PipelineManager] TTS unmuted call_id=%s", voice_call_id)
        return True

    def is_tts_muted(self, voice_call_id: int) -> bool:
        return self._tts_muted.get(voice_call_id, False)

    def is_active(self, voice_call_id: int) -> bool:
        task = self._tasks.get(voice_call_id)
        active = task is not None and not task.done()
        logger.debug("[PipelineManager] is_active call_id=%s → %s", voice_call_id, active)
        return active

    def active_calls(self) -> list[int]:
        calls = [cid for cid, t in self._tasks.items() if not t.done()]
        logger.debug("[PipelineManager] active_calls=%s", calls)
        return calls

    def _cleanup(self, voice_call_id: int) -> None:
        # Idempotency guard. _cleanup may run twice: once via add_done_callback
        # and once explicitly from .stop(). The second invocation must be a
        # no-op so future cleanup hooks don't have to be re-entrant.
        if voice_call_id in self._cleaned_up:
            return
        self._cleaned_up.add(voice_call_id)
        self._tasks.pop(voice_call_id, None)
        self._tts_muted.pop(voice_call_id, None)
        # Drop prewarmer cache + voice background-task tracker for this call
        try:
            from app.services.voice.pipecat.processors.context_prewarmer import (
                cleanup as _prewarm_cleanup,
            )
            _prewarm_cleanup(voice_call_id)
        except Exception:
            pass
        try:
            from app.services.chat.orchestrator import voice_call_cleanup
            voice_call_cleanup(voice_call_id)
        except Exception:
            pass
        logger.info("[PipelineManager] cleaned up call_id=%s", voice_call_id)


# Global singleton — one per worker process
pipeline_manager = PipelineManager()
