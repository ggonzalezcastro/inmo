"""
TranscriptSaver — saves each utterance to CallTranscript and broadcasts
via WebSocket to the broker's dashboard.

Handles both lead speech (TranscriptionFrame) and AI speech (TextFrame).
Strips Fish Audio emotion tags before saving to DB.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from pipecat.frames.frames import (
        Frame, TextFrame, TranscriptionFrame, InterimTranscriptionFrame,
        TTSTextFrame, AggregatedTextFrame,
        LLMFullResponseStartFrame, LLMFullResponseEndFrame,
    )
    from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
    _PIPECAT_AVAILABLE = True
except ImportError:
    _PIPECAT_AVAILABLE = False
    FrameProcessor = object  # type: ignore[misc,assignment]
    FrameDirection = None    # type: ignore[assignment]

# Only save plain TextFrames that originate from the CRM/LLM — skip all
# specialised subclasses (TranscriptionFrame = lead speech, TTSTextFrame =
# word-level TTS output, AggregatedTextFrame = TTS aggregator, etc.)
_AI_SAVE_EXCLUDE = (TranscriptionFrame, InterimTranscriptionFrame, TTSTextFrame, AggregatedTextFrame) if _PIPECAT_AVAILABLE else ()

# Regex to strip emotion tags like "[warm and enthusiastic]" from text before DB save
_EMOTION_TAG_RE = re.compile(r'^\[([^\]]+)\]\s*')


def _strip_emotion_tag(text: str) -> tuple[str, Optional[str]]:
    """Return (clean_text, emotion_tag_used) — tag is None if no tag present."""
    match = _EMOTION_TAG_RE.match(text)
    if match:
        return text[match.end():], match.group(1)
    return text, None


class TranscriptSaver(FrameProcessor):  # type: ignore[misc]
    """
    Intercepts utterances and saves them to call_transcripts + WebSocket.

    speaker_mode:
        "lead"  — only save TranscriptionFrame (lead speech)
        "ai"    — only save TextFrame (AI speech, strip emotion tag)
        "human" — only save TranscriptionFrame for diarized human-agent speech
    """

    def __init__(
        self,
        voice_call_id: int,
        broker_id: int,
        speaker_mode: str,  # "lead" | "ai" | "human"
        db_session_factory: Any,
        call_start_time: Optional[datetime] = None,
    ) -> None:
        if not _PIPECAT_AVAILABLE:
            raise ImportError("pipecat-ai is not installed.")
        super().__init__()
        self._voice_call_id = voice_call_id
        self._broker_id = broker_id
        self._speaker_mode = speaker_mode
        self._db_factory = db_session_factory
        self._call_start = call_start_time or datetime.now(timezone.utc)
        # AI streaming aggregation buffer. CRMLLMProcessor pushes one
        # TextFrame per sentence between LLMFullResponseStart/EndFrame; we
        # accumulate the chunks here and persist a single transcript line
        # per response so the saved transcript stays one-row-per-utterance.
        self._ai_response_buffer: list[str] = []
        self._ai_response_emotion: Optional[str] = None
        self._ai_response_active: bool = False

    def _seconds_from_start(self) -> float:
        return (datetime.now(timezone.utc) - self._call_start).total_seconds()

    async def _save_line(
        self,
        text: str,
        speaker: str,
        confidence: Optional[float] = None,
        emotion_tag_used: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        from app.models.voice_call import CallTranscript, SpeakerType
        from app.core.websocket_manager import ws_manager

        speaker_enum = {
            "lead": SpeakerType.CUSTOMER,
            "ai": SpeakerType.BOT,
            "human": SpeakerType.AGENT,
        }.get(speaker, SpeakerType.CUSTOMER)

        timestamp = self._seconds_from_start()

        try:
            async with self._db_factory() as db:
                line = CallTranscript(
                    voice_call_id=self._voice_call_id,
                    speaker=speaker_enum,
                    text=text,
                    timestamp=timestamp,
                    confidence=confidence,
                    emotion_tag_used=emotion_tag_used,
                    duration_ms=duration_ms,
                )
                db.add(line)
                await db.commit()
            logger.info(
                "[TranscriptSaver] saved speaker=%s t=%.1fs text=%r call_id=%s",
                speaker, timestamp, text[:80], self._voice_call_id,
            )
        except Exception as exc:
            logger.error("[TranscriptSaver] DB save failed call_id=%s: %s", self._voice_call_id, exc)

        # Real-time WebSocket broadcast
        try:
            await ws_manager.broadcast(
                broker_id=self._broker_id,
                event="call_transcript_line",
                data={
                    "voice_call_id": self._voice_call_id,
                    "speaker": speaker,
                    "text": text,
                    "timestamp": timestamp,
                    "emotion_tag_used": emotion_tag_used,
                },
            )
        except Exception as exc:
            logger.warning("[TranscriptSaver] WS broadcast failed: %s", exc)

    async def _flush_ai_response(self) -> None:
        """Persist accumulated streaming chunks as a single transcript line."""
        if not self._ai_response_buffer:
            return
        joined = " ".join(p.strip() for p in self._ai_response_buffer if p.strip()).strip()
        emotion = self._ai_response_emotion
        self._ai_response_buffer = []
        self._ai_response_emotion = None
        if not joined:
            return
        logger.debug(
            "[TranscriptSaver] ai response (aggregated) call_id=%s emotion=%r text=%r",
            self._voice_call_id, emotion, joined[:80],
        )
        await self._save_line(text=joined, speaker="ai", emotion_tag_used=emotion)

    async def process_frame(self, frame: Any, direction: Any) -> None:
        await super().process_frame(frame, direction)

        # Streaming response window: open buffer on Start, flush on End.
        if self._speaker_mode == "ai" and isinstance(frame, LLMFullResponseStartFrame):
            self._ai_response_active = True
            self._ai_response_buffer = []
            self._ai_response_emotion = None
            await self.push_frame(frame, direction)
            return
        if self._speaker_mode == "ai" and isinstance(frame, LLMFullResponseEndFrame):
            await self._flush_ai_response()
            self._ai_response_active = False
            await self.push_frame(frame, direction)
            return

        if self._speaker_mode in ("lead", "human") and isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if text:
                confidence = getattr(frame, "confidence", None)
                logger.debug(
                    "[TranscriptSaver] lead speech call_id=%s conf=%.2f text=%r",
                    self._voice_call_id, confidence or 0.0, text[:80],
                )
                await self._save_line(
                    text=text,
                    speaker=self._speaker_mode,
                    confidence=confidence,
                )
            else:
                logger.debug("[TranscriptSaver] empty transcription frame — skipped call_id=%s", self._voice_call_id)

        elif (
            self._speaker_mode == "ai"
            and isinstance(frame, TextFrame)
            and not isinstance(frame, _AI_SAVE_EXCLUDE)
        ):
            text = (frame.text or "").strip()
            if text:
                clean_text, emotion_tag = _strip_emotion_tag(text)
                if self._ai_response_active:
                    # Accumulate streaming chunk; persist on response-end.
                    if clean_text:
                        self._ai_response_buffer.append(clean_text)
                        if emotion_tag and not self._ai_response_emotion:
                            self._ai_response_emotion = emotion_tag
                else:
                    # Non-streaming legacy path — save inline.
                    logger.debug(
                        "[TranscriptSaver] ai response call_id=%s emotion=%r text=%r",
                        self._voice_call_id, emotion_tag, clean_text[:80],
                    )
                    if clean_text:
                        await self._save_line(
                            text=clean_text,
                            speaker="ai",
                            emotion_tag_used=emotion_tag,
                        )
            else:
                logger.debug("[TranscriptSaver] empty AI text frame — skipped call_id=%s", self._voice_call_id)
        else:
            logger.debug(
                "[TranscriptSaver] pass-through frame=%s mode=%s call_id=%s",
                type(frame).__name__, self._speaker_mode, self._voice_call_id,
            )

        await self.push_frame(frame, direction)
