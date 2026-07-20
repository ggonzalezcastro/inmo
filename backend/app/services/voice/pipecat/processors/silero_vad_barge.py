"""
VAD-based turn detection + barge-in support for the autonomous/handoff pipelines.

Two processors, always used together:

    VADProcessor(SileroVADAnalyzer)
        Runs Silero ML VAD on every InputAudioRawFrame.
        Broadcasts VADUserStartedSpeakingFrame / VADUserStoppedSpeakingFrame
        in both directions — STT service uses these for endpointing awareness.

    BargeinBridge
        Converts VADUserStartedSpeakingFrame → InterruptionFrame so the TTS
        service stops mid-utterance when the lead starts speaking (barge-in).

        Echo-suppression: Twilio MediaStream has no echo cancellation, so
        the bot's own TTS audio comes back through the input WebSocket and
        Silero VAD happily flags it as "user speaking", which would cancel
        the TTS 100–300 ms after it starts. We gate interruptions via
        BotStartedSpeakingFrame / BotStoppedSpeakingFrame: while the bot
        is speaking we require a grace window before allowing barge-in,
        and we drop any interruption that arrives within that window.

        Tunable via env `VOICE_BARGE_GRACE_MS` (default 1500 ms).
        Set `VOICE_BARGE_DISABLED=1` to disable barge-in entirely.

Usage (in pipeline builders):
    vad, barger = build_vad_processors(stop_secs=0.5)
    pipeline = Pipeline([transport.input(), vad, barger, stt, ...])
"""
from __future__ import annotations

import logging
import os
import time as _time
from typing import Any

logger = logging.getLogger(__name__)

try:
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.audio.vad.vad_analyzer import VADParams
    from pipecat.frames.frames import (
        BotStartedSpeakingFrame,
        BotStoppedSpeakingFrame,
        Frame,
        VADUserStartedSpeakingFrame,
    )
    from pipecat.processors.audio.vad_processor import VADProcessor
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
    _PIPECAT_AVAILABLE = True
except ImportError:
    _PIPECAT_AVAILABLE = False
    FrameProcessor = object  # type: ignore[misc,assignment]
    FrameDirection = None    # type: ignore[assignment]


class BargeinBridge(FrameProcessor):  # type: ignore[misc]
    """
    Converts VADUserStartedSpeakingFrame → broadcast_interruption(),
    with echo-suppression while the bot is itself speaking.

    State machine:
      - Track bot speaking state from BotStartedSpeakingFrame/BotStoppedSpeakingFrame.
      - While bot is speaking (or within `grace_ms` after start), drop any
        VADUserStartedSpeakingFrame — it is almost certainly bot-audio echo.
      - Once grace window has passed, allow real barge-in for long responses.
    """

    def __init__(self) -> None:
        super().__init__()
        self._bot_speaking = False
        self._bot_started_at: float = 0.0
        self._grace_ms = int(os.getenv("VOICE_BARGE_GRACE_MS", "1500"))
        self._disabled = os.getenv("VOICE_BARGE_DISABLED", "0") in ("1", "true", "True")

    async def process_frame(self, frame: Any, direction: Any) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
            self._bot_started_at = _time.monotonic()
            logger.debug("[BargeinBridge] bot started speaking — barge-in suppressed for %dms", self._grace_ms)

        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            logger.debug("[BargeinBridge] bot stopped speaking — barge-in re-armed")

        elif isinstance(frame, VADUserStartedSpeakingFrame):
            if self._disabled:
                logger.debug("[BargeinBridge] VAD user-start ignored (barge-in disabled)")
            elif self._bot_speaking:
                elapsed_ms = (_time.monotonic() - self._bot_started_at) * 1000
                if elapsed_ms < self._grace_ms:
                    logger.info(
                        "[BargeinBridge] suppressing barge-in: bot only speaking for %.0fms (grace=%dms) — likely echo",
                        elapsed_ms, self._grace_ms,
                    )
                else:
                    logger.debug(
                        "[BargeinBridge] real barge-in: bot speaking %.0fms — interrupting TTS",
                        elapsed_ms,
                    )
                    await self.broadcast_interruption()
            else:
                logger.debug("[BargeinBridge] user started speaking — interrupting TTS")
                await self.broadcast_interruption()

        await self.push_frame(frame, direction)


def build_vad_processors(stop_secs: float = 0.3) -> "tuple[VADProcessor, BargeinBridge]":
    """
    Build (VADProcessor, BargeinBridge) pair for insertion at the front of a pipeline.

    Parameters
    ----------
    stop_secs : silence in seconds required to trigger UserStoppedSpeaking (default 0.5).
                Increase to 0.7 if users complain the AI cuts them off.
                Decrease to 0.3 for faster response at the cost of more interruptions.

    Env overrides (for live tuning without code changes):
      VOICE_VAD_CONFIDENCE  (default 0.7) — higher = needs louder/clearer speech to trigger
      VOICE_VAD_START_SECS  (default 0.2) — longer = ignores short noises (cough, breath)
      VOICE_VAD_MIN_VOLUME  (default 0.4) — RMS threshold below which audio is silence
                                            (lowered for Twilio µ-law 8 kHz audio)
    """
    import os as _os

    if not _PIPECAT_AVAILABLE:
        raise ImportError(
            "pipecat-ai[silero] is not installed. "
            "Run: pip install 'pipecat-ai[deepgram,elevenlabs,fish,silero]'"
        )

    # Defaults tuned for Twilio µ-law 8 kHz audio (no echo cancellation, lower
    # effective RMS than studio audio). Earlier defaults of 0.8 / 0.6 were too
    # strict and swallowed quiet/distant speakers — barge-in then never fires
    # for them. Override per-deployment via env if needed.
    confidence = float(_os.getenv("VOICE_VAD_CONFIDENCE", "0.7"))
    start_secs = float(_os.getenv("VOICE_VAD_START_SECS", "0.2"))
    # Allow env override of stop_secs — research showed 0.5s adds 200ms
    # of unnecessary silence wait when Deepgram endpointing (150-300ms)
    # already fires speech_final earlier.
    stop_secs = float(_os.getenv("VOICE_VAD_STOP_SECS", str(stop_secs)))
    min_volume = float(_os.getenv("VOICE_VAD_MIN_VOLUME", "0.4"))

    logger.info(
        "[VAD] silero confidence=%.2f start_secs=%.2f stop_secs=%.2f min_volume=%.2f",
        confidence, start_secs, stop_secs, min_volume,
    )

    vad = VADProcessor(
        vad_analyzer=SileroVADAnalyzer(
            params=VADParams(
                confidence=confidence,
                start_secs=start_secs,
                stop_secs=stop_secs,
                min_volume=min_volume,
            )
        )
    )
    barger = BargeinBridge()
    return vad, barger
