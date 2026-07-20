"""SmartTurnEarlyStop — semantic end-of-turn detector for Pipecat pipelines.

Wraps :class:`pipecat.audio.turn.smart_turn.local_smart_turn_v3.LocalSmartTurnAnalyzerV3`
(bundled ONNX ``smart-turn-v3.2-cpu`` model) and emits an early
``UserStoppedSpeakingFrame`` when the model predicts the user has finished
talking — typically 100–300 ms before Silero VAD's ``stop_secs`` timer
would fire.

Pipeline placement (after VAD, before STT):

    transport.input() → vad → barger → SmartTurnEarlyStop → stt → ...

When the analyzer is unavailable (import error, model load failure) the
processor degrades to a pass-through and VAD timing remains authoritative.

Controlled by env vars:

* ``VOICE_SMART_TURN_ENABLED`` (default ``1``) — kill switch.
* ``VOICE_SMART_TURN_MIN_SPEECH_MS`` (default ``300``) — guard so we
  don't cut off very short utterances before the model has enough audio.

Docs:
  https://github.com/pipecat-ai/pipecat/blob/main/docs/api/api/pipecat.audio.turn.smart_turn.local_smart_turn_v3.md
  https://github.com/pipecat-ai/pipecat/blob/main/docs/api/api/pipecat.audio.turn.base_turn_analyzer.md
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


def smart_turn_enabled() -> bool:
    return os.getenv("VOICE_SMART_TURN_ENABLED", "1") not in ("0", "false", "False")


def build_smart_turn(sample_rate: int = 8000) -> Optional[Any]:
    """Return a SmartTurnEarlyStop processor or None if disabled/unavailable."""
    if not smart_turn_enabled():
        logger.info("[SmartTurn] disabled via env VOICE_SMART_TURN_ENABLED=0")
        return None
    try:
        from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import (
            LocalSmartTurnAnalyzerV3,
        )
        from pipecat.audio.turn.base_turn_analyzer import EndOfTurnState
        from pipecat.frames.frames import (
            Frame,
            AudioRawFrame,
            UserStartedSpeakingFrame,
            UserStoppedSpeakingFrame,
        )
        try:
            from pipecat.frames.frames import (
                VADUserStartedSpeakingFrame,
                VADUserStoppedSpeakingFrame,
            )
        except Exception:
            VADUserStartedSpeakingFrame = UserStartedSpeakingFrame  # type: ignore
            VADUserStoppedSpeakingFrame = UserStoppedSpeakingFrame  # type: ignore
        from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
    except Exception as exc:
        logger.warning("[SmartTurn] dependencies missing — disabled: %s", exc)
        return None

    try:
        analyzer = LocalSmartTurnAnalyzerV3()
        analyzer.set_sample_rate(sample_rate)
    except Exception as exc:
        logger.warning("[SmartTurn] analyzer init failed — disabled: %s", exc)
        return None

    # ── ONNX JIT warmup (one inference at boot so first real call is fast) ──
    try:
        t0 = time.perf_counter()
        analyzer.append_audio(b"\x00" * (sample_rate // 50 * 2), False)
        analyzer.clear()
        logger.info(
            "[SmartTurn] warmup ok sr=%d elapsed_ms=%d",
            sample_rate, int((time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        logger.warning("[SmartTurn] warmup failed (continuing): %s", exc)

    min_speech_ms = int(os.getenv("VOICE_SMART_TURN_MIN_SPEECH_MS", "300"))
    # Number of consecutive COMPLETE predictions required before we trust
    # the analyzer and emit an early-stop. Defaults to 2 — single-frame
    # COMPLETE flips are the dominant source of false positives that cause
    # the LLM to respond to a partial utterance and then speak again when
    # the user finishes the sentence.
    min_consensus = max(1, int(os.getenv("VOICE_SMART_TURN_CONSENSUS", "2")))

    class SmartTurnEarlyStop(FrameProcessor):
        """See module docstring."""

        def __init__(self, **kw: Any) -> None:
            super().__init__(**kw)
            self._analyzer = analyzer
            self._sr = sample_rate
            self._user_speaking = False
            self._early_stopped = False
            self._speech_start: Optional[float] = None
            self._early_count = 0
            self._consecutive_complete = 0

        async def process_frame(self, frame: Any, direction: Any) -> None:
            await super().process_frame(frame, direction)

            if isinstance(frame, (UserStartedSpeakingFrame, VADUserStartedSpeakingFrame)):
                self._user_speaking = True
                self._early_stopped = False
                self._consecutive_complete = 0
                self._speech_start = time.perf_counter()
                try:
                    self._analyzer.clear()
                except Exception:
                    pass
                await self.push_frame(frame, direction)
                return

            if isinstance(frame, (UserStoppedSpeakingFrame, VADUserStoppedSpeakingFrame)):
                if self._early_stopped:
                    # We already emitted an early UserStoppedSpeakingFrame for
                    # this turn; suppress the late VAD-driven stop to avoid
                    # double-triggering downstream LLM processors (re-introducing
                    # the Bug B coalescing problem from call 39).
                    self._early_stopped = False
                    self._consecutive_complete = 0
                    logger.debug("[SmartTurn] suppressed late VAD stop after early-stop")
                    return
                self._user_speaking = False
                self._speech_start = None
                self._consecutive_complete = 0
                await self.push_frame(frame, direction)
                return

            if (
                isinstance(frame, AudioRawFrame)
                and self._user_speaking
                and direction == FrameDirection.DOWNSTREAM
            ):
                speech_ms = (
                    int((time.perf_counter() - self._speech_start) * 1000)
                    if self._speech_start else 0
                )
                try:
                    state = self._analyzer.append_audio(frame.audio, True)
                except Exception:
                    state = None

                if state == EndOfTurnState.COMPLETE:
                    self._consecutive_complete += 1
                else:
                    # Single non-COMPLETE breaks consensus → reset.
                    self._consecutive_complete = 0

                if (
                    self._consecutive_complete >= min_consensus
                    and speech_ms >= min_speech_ms
                ):
                    self._user_speaking = False
                    self._early_stopped = True
                    self._speech_start = None
                    self._early_count += 1
                    self._consecutive_complete = 0
                    logger.info(
                        "[SmartTurn] early-stop #%d speech_ms=%d consensus=%d (vs VAD wait)",
                        self._early_count, speech_ms, min_consensus,
                    )
                    # Push the in-flight audio first so STT sees it, then the
                    # synthetic stop so downstream aggregators finalize.
                    await self.push_frame(frame, direction)
                    await self.push_frame(UserStoppedSpeakingFrame(), direction)
                    try:
                        self._analyzer.clear()
                    except Exception:
                        pass
                    return

            await self.push_frame(frame, direction)

    return SmartTurnEarlyStop()
