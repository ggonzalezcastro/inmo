"""
FillerPlayer — emits a short filler utterance ("a ver", "mmm", "claro")
immediately after the lead finishes a turn, while the LLM is still
generating the real response.

This is a *perceived-latency* optimization: the lead hears the bot start
talking within ~500 ms (just the TTS round-trip on a short token) instead
of waiting for the full LLM + TTS pipeline (~3–4 s).

Pipeline placement:
    transport.input → vad → barger → stt → ts_lead
        → FillerPlayer            ← here, AFTER ts_lead, BEFORE CRMLLMProcessor
        → crm → emotion → ts_ai → tts → transport.output

Behaviour:
- On a TranscriptionFrame with `is_final=True` and message ≥ 3 words,
  push a TextFrame with a short filler downstream (it will hit TTS
  while CRM is computing).
- The filler is debounced per-utterance; we don't fire on interim frames.
- Fillers are randomly sampled from a small list to avoid sounding robotic.

Disabled when env `VOICE_FILLER_ENABLED=0`.
"""
from __future__ import annotations

import logging
import os
import random
from typing import Any, List

logger = logging.getLogger(__name__)

try:
    from pipecat.frames.frames import Frame, TextFrame, TranscriptionFrame
    from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
    _PIPECAT_AVAILABLE = True
except ImportError:
    _PIPECAT_AVAILABLE = False
    FrameProcessor = object  # type: ignore[misc,assignment]
    FrameDirection = None    # type: ignore[assignment]


# Short, neutral, voice-friendly fillers in Chilean Spanish.
# Keep < ~10 chars so TTS finishes before the real LLM response arrives.
_DEFAULT_FILLERS: List[str] = [
    "Mmm.",
    "A ver.",
    "Claro.",
    "Ya.",
    "Mmm, déjame ver.",
]


def _is_enabled() -> bool:
    # Disabled by default: with CRMLLMProcessor blocking the frame queue on
    # the LLM call, the filler TextFrame queues *behind* the real response
    # and reaches TTS *after* it — no perceived-latency win, just extra noise.
    # Re-enable only when the pipeline supports a parallel out-of-band path.
    return os.getenv("VOICE_FILLER_ENABLED", "0") not in ("0", "false", "False")


class FillerPlayer(FrameProcessor):  # type: ignore[misc]
    """
    Emits a quick filler TextFrame right after a final transcription so the
    TTS starts speaking while the LLM is still computing the real response.
    """

    def __init__(
        self,
        *,
        min_words: int = 3,
        cooldown_seconds: float = 4.0,
        fillers: List[str] | None = None,
    ) -> None:
        if not _PIPECAT_AVAILABLE:
            raise ImportError(
                "pipecat-ai is not installed. Run: pip install pipecat-ai[deepgram,fish]"
            )
        super().__init__()
        self._min_words = max(1, int(min_words))
        self._cooldown = max(0.0, float(cooldown_seconds))
        self._fillers = list(fillers) if fillers else list(_DEFAULT_FILLERS)
        self._last_fired_at: float = 0.0

    async def process_frame(self, frame: Any, direction: Any) -> None:
        await super().process_frame(frame, direction)

        # Always pass the frame through — fillers are *additional* output.
        await self.push_frame(frame, direction)

        if not _is_enabled():
            return
        if not isinstance(frame, TranscriptionFrame):
            return
        # Only fire on final transcripts (interim re-emissions skipped).
        if getattr(frame, "is_final", True) is False:
            return

        text = (getattr(frame, "text", "") or "").strip()
        if not text:
            return
        word_count = len(text.split())
        if word_count < self._min_words:
            # Skip on trivial yes/no — LLM is fast enough.
            return

        # Cooldown: avoid double-fillers if STT emits two finals close together.
        import time as _time
        now = _time.monotonic()
        if (now - self._last_fired_at) < self._cooldown:
            return
        self._last_fired_at = now

        filler = random.choice(self._fillers)
        logger.info(
            "[FillerPlayer] firing filler=%r words=%d (mask LLM latency)",
            filler, word_count,
        )
        try:
            await self.push_frame(TextFrame(text=filler), direction)
        except Exception as exc:
            logger.warning("[FillerPlayer] push failed: %s", exc)


def build_filler_player() -> "FillerPlayer":
    """Factory used by pipeline builders."""
    return FillerPlayer()
