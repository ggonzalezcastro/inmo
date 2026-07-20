"""
EmotionTagger — injects Fish Audio S2 emotion tags into AI response text.

Receives TextFrame from CRMLLMProcessor, determines the appropriate
emotion tag based on agent type + lead sentiment, and prepends the tag
to the text before forwarding to TTS.

Fish Audio S2 supports open-domain emotion descriptions in brackets:
    [warm and enthusiastic] Hola Juan, encontré opciones increíbles para ti.
    [empathetic and calm] Entiendo tu preocupación, déjame ayudarte.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Emoji regex — matches any Unicode emoji/pictograph character
_EMOJI_RE = re.compile(
    "[\U00010000-\U0010ffff"      # Supplementary Multilingual Plane
    "\U0001F600-\U0001F64F"       # Emoticons
    "\U0001F300-\U0001F5FF"       # Misc symbols & pictographs
    "\U0001F680-\U0001F6FF"       # Transport & map
    "\U0001F1E0-\U0001F1FF"       # Flags
    "\U00002702-\U000027B0"       # Dingbats
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)


def _strip_emojis(text: str) -> str:
    """Remove emoji characters that break TTS sentence aggregation."""
    return _EMOJI_RE.sub("", text).strip()


_MD_BOLD_RE = re.compile(r"\*{1,3}(.+?)\*{1,3}")
_MD_UNDERLINE_RE = re.compile(r"_{1,2}(.+?)_{1,2}")
_MD_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_CODE_RE = re.compile(r"`[^`]+`")


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting so TTS reads clean spoken text."""
    text = _MD_BOLD_RE.sub(r"\1", text)
    text = _MD_UNDERLINE_RE.sub(r"\1", text)
    text = _MD_HEADING_RE.sub("", text)
    text = _MD_LINK_RE.sub(r"\1", text)
    text = _MD_CODE_RE.sub("", text)
    # Collapse newlines into natural sentence pauses
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\n", " ", text)
    # Remove leftover lone asterisks/underscores
    text = re.sub(r"[*_~`#]", "", text)
    return re.sub(r"\s{2,}", " ", text).strip()

try:
    from pipecat.frames.frames import (
        Frame,
        TextFrame,
        TranscriptionFrame,
        InterimTranscriptionFrame,
        LLMFullResponseStartFrame,
        LLMFullResponseEndFrame,
    )
    from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
    _PIPECAT_AVAILABLE = True
except ImportError:
    _PIPECAT_AVAILABLE = False
    FrameProcessor = object  # type: ignore[misc,assignment]
    FrameDirection = None    # type: ignore[assignment]

# Emotion context → Fish Audio open-domain tag
_EMOTION_MAP: Dict[str, str] = {
    "qualifier_greeting": "warm and friendly",
    "qualifier_data_collection": "calm and professional",
    "qualifier_dicom_clean": "warm and reassuring",
    "qualifier_dicom_dirty": "empathetic and calm",
    "property_showing": "warm and enthusiastic",
    "property_zero_results": "calm and helpful",
    "scheduler_proposing": "cheerful and professional",
    "scheduler_confirmed": "cheerful and warm",
    "follow_up_reminder": "warm and friendly",
    "follow_up_post_visit": "curious and warm",
    "lead_frustrated": "empathetic and calm",
    "lead_goodbye": "warm and friendly",
    "default": "warm and professional",
}

# Agent type → default emotion context key
_AGENT_DEFAULT_CONTEXT: Dict[str, str] = {
    "qualifier": "qualifier_data_collection",
    "property": "property_showing",
    "scheduler": "scheduler_proposing",
    "follow_up": "follow_up_reminder",
}


def _detect_context(text: str, agent_type: Optional[str], sentiment: Optional[str]) -> str:
    """Heuristic context detection from response text and metadata."""
    lower = text.lower()

    if sentiment in ("frustrated", "angry", "negative"):
        return "lead_frustrated"

    if any(kw in lower for kw in ("adiós", "adios", "hasta luego", "cuídate", "cuidate", "que te vaya")):
        return "lead_goodbye"

    if agent_type == "scheduler":
        if any(kw in lower for kw in ("quedamos", "agendado", "confirmado", "cita")):
            return "scheduler_confirmed"
        return "scheduler_proposing"

    if agent_type == "property":
        if any(kw in lower for kw in ("no encontré", "no encontre", "no tenemos", "no hay disponible")):
            return "property_zero_results"
        return "property_showing"

    if agent_type == "qualifier":
        if any(kw in lower for kw in ("hola", "encantada", "bienvenido")):
            return "qualifier_greeting"
        if any(kw in lower for kw in ("dicom", "deuda", "regularizar")):
            if any(neg in lower for neg in ("no puedo", "no podemos", "debes regularizar")):
                return "qualifier_dicom_dirty"
            return "qualifier_dicom_clean"
        return "qualifier_data_collection"

    return _AGENT_DEFAULT_CONTEXT.get(agent_type or "", "default")


class EmotionTagger(FrameProcessor):  # type: ignore[misc]
    """
    Prepends a Fish Audio emotion tag to each AI TextFrame.

    The tag format is: [emotion description] rest of text
    Tags are stripped from what gets saved to CallTranscript — only
    the clean text is stored in DB.

    When tts_provider != "fish_audio" (e.g. "elevenlabs"), tag injection
    is skipped — ElevenLabs ignores the bracket format or reads it aloud.
    """

    def __init__(self, broker_id: int, tts_provider: str = "fish_audio") -> None:
        if not _PIPECAT_AVAILABLE:
            raise ImportError("pipecat-ai is not installed.")
        super().__init__()
        self._broker_id = broker_id
        self._tts_provider = tts_provider.lower()
        # Only Fish s2 family honors `[emotion]` prosody tags. s1 reads
        # them as literal text ("warm and friendly"). Default off unless
        # explicitly enabled or model starts with "s2".
        _fish_model = (__import__("os").getenv("FISH_AUDIO_MODEL", "s1") or "s1").lower()
        _emotion_env = (__import__("os").getenv("VOICE_EMOTION_TAGS_ENABLED", "auto") or "auto").lower()
        if _emotion_env == "1" or _emotion_env == "true":
            self._emotion_enabled = True
        elif _emotion_env == "0" or _emotion_env == "false":
            self._emotion_enabled = False
        else:
            self._emotion_enabled = _fish_model.startswith("s2")
        if not self._emotion_enabled:
            logger.info(
                "[EmotionTagger] tags DISABLED broker=%s model=%s — Fish s1 doesn't "
                "honor [emotion] syntax; tags would be spoken as text.",
                broker_id, _fish_model,
            )
        self._last_sentiment: Optional[str] = None
        # Tracks whether we've already injected an emotion tag for the current
        # LLM response window. With streaming, the LLM emits multiple TextFrames
        # per response; we only want to tag the FIRST one (Fish TTS treats the
        # tag as a per-utterance voice directive — repeating it on every chunk
        # would cause the model to re-narrate "warm and friendly" or reset
        # prosody between sentences).
        self._response_tagged: bool = False

    def update_sentiment(self, sentiment: str) -> None:
        """Called by TranscriptSaver when new lead sentiment is detected."""
        self._last_sentiment = sentiment

    async def process_frame(self, frame: Any, direction: Any) -> None:
        await super().process_frame(frame, direction)

        # Track LLM response window so we only tag the first TextFrame in
        # a streaming response.
        if isinstance(frame, LLMFullResponseStartFrame):
            self._response_tagged = False
            await self.push_frame(frame, direction)
            return
        if isinstance(frame, LLMFullResponseEndFrame):
            self._response_tagged = False
            await self.push_frame(frame, direction)
            return

        if not isinstance(frame, TextFrame):
            await self.push_frame(frame, direction)
            return

        # TranscriptionFrames are lead speech — never tag them for TTS
        if isinstance(frame, (TranscriptionFrame, InterimTranscriptionFrame)):
            await self.push_frame(frame, direction)
            return

        text = frame.text or ""
        # Strip emojis and markdown — both break TTS sentence aggregation
        text = _strip_emojis(text)
        text = _strip_markdown(text)
        if not text.strip():
            # Frame was ONLY emoji/markdown — drop it entirely instead of
            # passing the dirty original through. This prevents emojis
            # from leaking into the saved transcript (and into Fish TTS,
            # which can mispronounce them).
            logger.debug(
                "[EmotionTagger] frame stripped to empty — dropped broker=%s original=%r",
                self._broker_id, (frame.text or "")[:40],
            )
            return

        is_streaming_chunk = bool(
            getattr(frame, "_crm_metadata", None)
            and frame._crm_metadata.get("streaming_chunk")  # type: ignore[attr-defined]
        )

        # Skip tag if: emotion-tagging disabled (e.g. Fish s1); already
        # tagged literally; not Fish provider; OR this is a streaming chunk
        # and we already tagged the first chunk of the current response window.
        if (
            not self._emotion_enabled
            or re.match(r'^\[.+?\]', text)
            or self._tts_provider != "fish_audio"
            or (is_streaming_chunk and self._response_tagged)
        ):
            clean_frame = TextFrame(text=text)
            if hasattr(frame, "_crm_metadata"):
                clean_frame._crm_metadata = frame._crm_metadata  # type: ignore[attr-defined]
            await self.push_frame(clean_frame, direction)
            return

        agent_type = getattr(frame, "_crm_metadata", {}).get("agent_type") if hasattr(frame, "_crm_metadata") else None
        context_key = _detect_context(text, agent_type, self._last_sentiment)
        tag = _EMOTION_MAP.get(context_key, _EMOTION_MAP["default"])

        tagged_frame = TextFrame(text=f"[{tag}] {text}")
        if hasattr(frame, "_crm_metadata"):
            tagged_frame._crm_metadata = {**(frame._crm_metadata or {}), "emotion_tag": tag}  # type: ignore[attr-defined]

        if is_streaming_chunk:
            self._response_tagged = True

        logger.debug(
            "[EmotionTagger] context=%s tag=%r agent=%s broker=%s streaming=%s",
            context_key, tag, agent_type, self._broker_id, is_streaming_chunk,
        )
        await self.push_frame(tagged_frame, direction)
