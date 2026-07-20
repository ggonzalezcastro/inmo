"""
CRMLLMProcessor — bridges Pipecat transcription frames to the CRM multi-agent system.

Receives TranscriptionFrame from Deepgram STT, calls
ChatOrchestratorService.process_for_voice(), and emits a TextFrame with
the AI response for downstream processors (EmotionTagger → TTS).
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Stalling fillers the LLM tends to emit at the start of a turn. They add
# 200–400 ms of dead-air per turn ("A ver. Perfecto, …") with no value, so
# we strip them in post-processing. Match is case-insensitive at start only.
_LLM_FILLER_RE = re.compile(
    r"^\s*(?:a\s*ver|mmm+|eh+|este+|claro|ya|bueno|ok|okay|déjame\s+ver|dejame\s+ver)"
    r"[\s,\.!\?\u2026:;]+",
    re.IGNORECASE,
)

# Sentence boundary detector for incremental TTS flushing during streaming.
# Matches terminal punctuation followed by whitespace OR end-of-string.
# Used inside CRMLLMProcessor's streaming callback to flush sentence-by-sentence
# instead of one TextFrame per token (which would defeat sentence aggregation).
_SENTENCE_FLUSH_RE = re.compile(r"[\.!\?\u2026][\"'\)\]]?\s")


# --- TTS pronunciation helpers ----------------------------------------------
# Fish TTS (and most neural TTS) reads emails / urls / "word.word" tokens
# letter-by-letter because the dot character without surrounding whitespace
# is treated as initialism. We convert those to spoken Spanish before push.
_EMAIL_RE = re.compile(r"\b([a-zA-Z0-9._%+\-]+)@([a-zA-Z0-9.\-]+)\.([a-zA-Z]{2,})\b")
_URL_DOT_RE = re.compile(r"\b(www)\.([a-zA-Z0-9\-]+)\.([a-zA-Z]{2,})\b")


def _spell_email_match(m: "re.Match[str]") -> str:
    local = m.group(1).replace(".", " punto ").replace("_", " guion bajo ").replace("-", " guion ")
    domain = m.group(2).replace(".", " punto ").replace("-", " guion ")
    tld = m.group(3)
    return f"{local} arroba {domain} punto {tld}"


def _humanize_for_tts(text: str) -> str:
    """Rewrite tokens that TTS would spell letter-by-letter into spoken form.

    Converts emails like ``user.name@gmail.com`` → ``user punto name arroba
    gmail punto com`` so Fish TTS reads them naturally instead of spelling.
    """
    if not text:
        return text
    out = _EMAIL_RE.sub(_spell_email_match, text)
    out = _URL_DOT_RE.sub(lambda m: f"{m.group(1)} punto {m.group(2)} punto {m.group(3)}", out)
    return out


def _strip_llm_fillers(text: str) -> str:
    """Remove leading stalling fillers like 'A ver.', 'Mmm,', 'Claro,' …"""
    prev = None
    out = text
    # Loop so we strip stacked fillers like "Mmm. A ver. Perfecto..."
    while prev != out:
        prev = out
        out = _LLM_FILLER_RE.sub("", out)
    return out.lstrip()


# Sentence splitter — handles Spanish (¿…? ¡…!), ellipsis (.., …), and
# preserves opening punctuation with the next sentence ("¿Qué día …?").
# We split on terminal punctuation followed by whitespace OR end-of-string.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.!\?\u2026])\s+(?=\S)")


def _split_into_sentences(text: str) -> List[str]:
    """
    Split LLM output into sentences for incremental TTS.

    Pushing each sentence as its own TextFrame ensures Fish TTS' aggregator
    flushes every sentence (it would otherwise buffer the trailing one),
    and lets the first sentence start playing while later ones are still
    being synthesized — measurable TTFB win for multi-sentence responses.
    """
    text = (text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text) if p.strip()]
    return parts or [text]

# Pipecat imports are optional at module load time — the module can be imported
# without pipecat installed; it will fail at instantiation time only.
try:
    from pipecat.frames.frames import (
        Frame,
        TextFrame,
        TranscriptionFrame,
        ErrorFrame,
        LLMFullResponseStartFrame,
        LLMFullResponseEndFrame,
    )
    from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
    _PIPECAT_AVAILABLE = True
except ImportError:
    _PIPECAT_AVAILABLE = False
    FrameProcessor = object  # type: ignore[misc,assignment]
    FrameDirection = None    # type: ignore[assignment]


_FALLBACK_RESPONSE = "Disculpa, ¿me lo puedes repetir?"


class CRMLLMProcessor(FrameProcessor):  # type: ignore[misc]
    """
    Connects Pipecat's STT output to the CRM AgentSupervisor.

    Flow:
        TranscriptionFrame (lead speech)
          → process_for_voice()       (AgentSupervisor handles it)
          → TextFrame (AI response)   (forwarded to EmotionTagger)

    The processor uses a lazily-injected db session factory so it can
    be constructed before the async DB session is available.
    """

    def __init__(
        self,
        lead_id: int,
        broker_id: int,
        voice_call_id: int,
        db_session_factory: Any,  # async callable → AsyncSession
        pipeline_manager: Any = None,
        handoff_monitor: Any = None,
        emotion_tagger: Any = None,
        call_purpose: Optional[str] = None,
    ) -> None:
        if not _PIPECAT_AVAILABLE:
            raise ImportError("pipecat-ai is not installed. Run: pip install pipecat-ai[fish,deepgram,twilio]")
        super().__init__()
        self._lead_id = lead_id
        self._broker_id = broker_id
        self._voice_call_id = voice_call_id
        self._db_factory = db_session_factory
        self._pipeline_manager = pipeline_manager
        self._handoff_monitor = handoff_monitor
        self._emotion_tagger = emotion_tagger
        self._call_purpose = call_purpose
        self._last_agent_type: Optional[str] = None
        # Turn-coalescing debouncer. Deepgram may emit several
        # TranscriptionFrames for one "user turn" if the user pauses
        # briefly between sentences (endpointing=300ms). We collect
        # frames into _pending_text and only fire the LLM after
        # COALESCE_MS of silence — collapsing "Hola." + "Para mañana."
        # into a single turn instead of two duplicate responses.
        import os as _os
        self._coalesce_ms = int(_os.getenv("VOICE_TURN_COALESCE_MS", "350"))
        self._pending_text: List[str] = []
        self._pending_task: Optional[asyncio.Task] = None
        self._pending_lock = asyncio.Lock()
        # True once a debounced turn has left its sleep and is running the LLM.
        # While set, new transcriptions must NOT cancel the task (cancelling
        # mid-stream raises CancelledError, which the turn's `except Exception`
        # does not catch, leaving an unmatched LLMFullResponseStartFrame and a
        # stuck TranscriptSaver). Instead we buffer and let the turn reschedule.
        self._turn_in_progress = False

    async def process_frame(self, frame: Any, direction: Any) -> None:
        await super().process_frame(frame, direction)

        if not isinstance(frame, TranscriptionFrame):
            await self.push_frame(frame, direction)
            return

        # Skip empty transcriptions
        text = (frame.text or "").strip()
        if not text:
            logger.debug("[CRMLLMProcessor] empty transcription — skipped lead=%s", self._lead_id)
            return

        # Append to pending buffer and (re)schedule processing in
        # COALESCE_MS. If another transcription arrives in that window
        # we cancel the prior task and reschedule — preserving the
        # combined utterance as a single LLM turn.
        async with self._pending_lock:
            self._pending_text.append(text)
            # If a turn is already running the LLM, don't cancel it — just let
            # the buffered text be picked up when that turn reschedules.
            if self._turn_in_progress:
                return
            # Otherwise the pending task is still in its debounce sleep; cancel
            # and reschedule to extend the coalescing window.
            if self._pending_task and not self._pending_task.done():
                self._pending_task.cancel()
            self._pending_task = asyncio.create_task(
                self._debounced_process(direction)
            )

    async def _debounced_process(self, direction: Any) -> None:
        """Wait COALESCE_MS, then process accumulated pending text."""
        try:
            await asyncio.sleep(self._coalesce_ms / 1000.0)
        except asyncio.CancelledError:
            return
        async with self._pending_lock:
            if not self._pending_text:
                return
            text = " ".join(p.strip() for p in self._pending_text if p.strip()).strip()
            self._pending_text = []
            if not text:
                return
            # Claim the turn so incoming frames buffer instead of cancelling us.
            self._turn_in_progress = True
        try:
            await self._process_turn(text, direction)
        finally:
            async with self._pending_lock:
                self._turn_in_progress = False
                # Transcriptions that arrived while we were processing are still
                # buffered — schedule another debounced turn to handle them.
                if self._pending_text:
                    self._pending_task = asyncio.create_task(
                        self._debounced_process(direction)
                    )

    async def _process_turn(self, text: str, direction: Any) -> None:
        logger.info(
            "[CRMLLMProcessor] lead=%s msg=%r", self._lead_id, text[:80]
        )

        # Per-turn active flag — defined outside the try so the finally
        # block can always reference it even when imports fail at the top
        # of the try block.
        turn_active = [True]
        ai_text = _FALLBACK_RESPONSE
        stream_started = False
        stream_aborted = False
        sentences_pushed: List[str] = []
        stream_buf: List[str] = []

        try:
            from app.services.chat.orchestrator import ChatOrchestratorService
            from app.services.llm.streaming_context import (
                set_text_stream_callback,
                reset_text_stream_callback,
            )
            import os as _os

            t0 = time.perf_counter()
            t_db = t_llm_done = 0.0
            t_first_token: Optional[float] = None

            # Streaming can be force-disabled via env if it misbehaves.
            streaming_enabled = _os.getenv("VOICE_LLM_STREAMING_ENABLED", "1") != "0"

            # Sentence-flushing buffer for streaming text deltas. As tokens
            # arrive from the LLM we accumulate them; when the buffer ends
            # with a terminal punctuation ".!?…", we flush the sentence to
            # the pipeline as a TextFrame so Fish TTS' sentence aggregator
            # can start synthesising it while the rest of the response is
            # still being generated. (Buffers/flags are pre-declared at the
            # top of the function; we just reset them here.)
            stream_buf.clear()
            sentences_pushed.clear()
            stream_started = False
            stream_aborted = False
            stream_lock = asyncio.Lock()

            async def _on_text_delta(delta: str) -> None:
                nonlocal t_first_token, stream_started, stream_aborted
                if not turn_active[0]:
                    return
                if stream_aborted:
                    return
                # If the pipeline was muted mid-stream (e.g. handoff fired
                # while we were already speaking) silently drop the rest of
                # the response. We still record TTFT for observability.
                if (
                    self._pipeline_manager
                    and self._pipeline_manager.is_tts_muted(self._voice_call_id)
                ):
                    stream_aborted = True
                    return
                if t_first_token is None:
                    t_first_token = time.perf_counter() - t0
                    logger.info(
                        "[CRMLLMProcessor] first-token call=%s lead=%s ttft_ms=%d",
                        self._voice_call_id, self._lead_id, int(t_first_token * 1000),
                    )
                async with stream_lock:
                    if not stream_started:
                        await self.push_frame(LLMFullResponseStartFrame(), direction)
                        stream_started = True
                    stream_buf.append(delta)
                    joined = "".join(stream_buf)
                    # Flush at sentence boundary (terminal punctuation followed
                    # by space or end-of-buffer). We require a trailing space
                    # so we don't flush mid-abbreviation ("Sr. " stays open).
                    if _SENTENCE_FLUSH_RE.search(joined):
                        # Find the LAST flush point in the buffer.
                        match = list(_SENTENCE_FLUSH_RE.finditer(joined))[-1]
                        flush_to = match.end()
                        sentence = joined[:flush_to].strip()
                        remainder = joined[flush_to:]
                        if sentence:
                            sentence = _strip_llm_fillers(sentence) if not sentences_pushed else sentence
                            if sentence:
                                sentences_pushed.append(sentence)
                                tf = TextFrame(text=_humanize_for_tts(sentence))
                                tf._crm_metadata = {  # type: ignore[attr-defined]
                                    "agent_type": self._last_agent_type,
                                    "streaming_chunk": True,
                                }
                                await self.push_frame(tf, direction)
                        stream_buf.clear()
                        if remainder:
                            stream_buf.append(remainder)

            cb_token = set_text_stream_callback(_on_text_delta) if streaming_enabled else None
            try:
                async with self._db_factory() as db:
                    t_db = time.perf_counter() - t0
                    result = await ChatOrchestratorService.process_for_voice(
                        db=db,
                        lead_id=self._lead_id,
                        broker_id=self._broker_id,
                        message=text,
                        voice_call_id=self._voice_call_id,
                        call_purpose=self._call_purpose,
                    )
            finally:
                if cb_token is not None:
                    reset_text_stream_callback(cb_token)
            t_llm_done = time.perf_counter() - t0
            elapsed = t_llm_done

            ai_text = result.response if result else _FALLBACK_RESPONSE
            ai_text = _strip_llm_fillers(ai_text)
            agent_type = (
                result.metadata.get("agent_type")
                if result and result.metadata
                else None
            )
            self._last_agent_type = agent_type

            logger.info(
                "[CRMLLMProcessor] lead=%s agent=%s latency=%.2fs ttft=%.2fs db_open=%.2fs response=%r",
                self._lead_id, agent_type, elapsed,
                t_first_token if t_first_token is not None else -1.0,
                t_db, ai_text[:80],
            )
            # Structured one-liner for grepping latency in production logs.
            logger.info(
                "[VOICE-LATENCY] call=%s lead=%s stage=process_for_voice total_ms=%d ttft_ms=%d db_open_ms=%d msg_words=%d streamed_sentences=%d",
                self._voice_call_id, self._lead_id,
                int(elapsed * 1000),
                int((t_first_token or 0) * 1000),
                int(t_db * 1000), len((text or '').split()),
                len(sentences_pushed),
            )

            # Wire context updates to HandoffMonitor so score-based triggers work
            if self._handoff_monitor and result and result.metadata:
                self._handoff_monitor.update_from_context(result.metadata)

            # Update emotion tagger with detected sentiment (if any)
            if self._emotion_tagger and result and result.metadata:
                sentiment = result.metadata.get("sentiment")
                if sentiment:
                    logger.debug("[CRMLLMProcessor] lead=%s sentiment=%s", self._lead_id, sentiment)
                    self._emotion_tagger.update_sentiment(sentiment)

        except Exception as exc:
            logger.error(
                "[CRMLLMProcessor] error lead=%s: %s", self._lead_id, exc, exc_info=True
            )
            ai_text = _FALLBACK_RESPONSE
            # If we already opened a streaming response window, close it
            # cleanly here. Otherwise the non-stream fallback below would
            # push a *second* LLMFullResponseStartFrame, leaving an unmatched
            # Start in the frame protocol and desynchronising EmotionTagger /
            # TranscriptSaver state.
            if stream_started:
                try:
                    await self.push_frame(LLMFullResponseEndFrame(), direction)
                except Exception:
                    pass
            stream_started = False
            stream_aborted = False
            sentences_pushed = []
            stream_buf = []
        finally:
            # Deactivate the per-turn callback so any background LLM task
            # launched by the supervisor can no longer push TextFrames into
            # the pipeline. This guards against ContextVar inheritance via
            # asyncio.create_task (the snapshot keeps the old callback
            # reachable; we make it a no-op explicitly).
            try:
                turn_active[0] = False
            except Exception:
                pass

        # Check if TTS is muted (handoff mode after transfer)
        if self._pipeline_manager and self._pipeline_manager.is_tts_muted(self._voice_call_id):
            logger.info("[CRMLLMProcessor] TTS muted — suppressing response call_id=%s", self._voice_call_id)
            # If we already started a stream, close it cleanly.
            if stream_started:
                await self.push_frame(LLMFullResponseEndFrame(), direction)
            return

        if stream_started:
            # Streaming path: flush any remaining buffered tail, then close
            # the LLM response window.
            if not stream_aborted:
                tail = "".join(stream_buf).strip()
                if tail:
                    tf = TextFrame(text=_humanize_for_tts(tail))
                    tf._crm_metadata = {  # type: ignore[attr-defined]
                        "agent_type": self._last_agent_type,
                        "streaming_chunk": True,
                    }
                    sentences_pushed.append(tail)
                    await self.push_frame(tf, direction)
            # Detect divergence between what was streamed and what the
            # supervisor actually returned (multi-agent handoff can
            # replace the response). If they differ noticeably the user
            # may hear stale text. Logged for now; not auto-recovered.
            spoken = " ".join(sentences_pushed).strip()
            if ai_text and spoken and len(ai_text) > 0:
                # rough similarity by length ratio
                ratio = min(len(spoken), len(ai_text)) / max(len(spoken), len(ai_text))
                if ratio < 0.6:
                    logger.warning(
                        "[CRMLLMProcessor] stream/result divergence call=%s "
                        "spoken_len=%d result_len=%d ratio=%.2f — possible "
                        "multi-agent handoff replaced response mid-stream",
                        self._voice_call_id, len(spoken), len(ai_text), ratio,
                    )
            logger.debug(
                "[CRMLLMProcessor] stream end call=%s lead=%s sentences=%d aborted=%s",
                self._voice_call_id, self._lead_id, len(sentences_pushed), stream_aborted,
            )
            await self.push_frame(LLMFullResponseEndFrame(), direction)
            return

        # Non-streaming fallback (used when LLM provider didn't stream — e.g.
        # Gemini/Claude legacy providers that don't honour the callback, or
        # when an exception aborted streaming before the first token).
        response_frame = TextFrame(text=_humanize_for_tts(ai_text))
        response_frame._crm_metadata = {"agent_type": self._last_agent_type}  # type: ignore[attr-defined]
        sentences = _split_into_sentences(response_frame.text)
        logger.debug(
            "[CRMLLMProcessor] pushing TextFrame to TTS lead=%s sentences=%d (non-stream)",
            self._lead_id, len(sentences),
        )
        await self.push_frame(LLMFullResponseStartFrame(), direction)
        await self.push_frame(response_frame, direction)
        await self.push_frame(LLMFullResponseEndFrame(), direction)
