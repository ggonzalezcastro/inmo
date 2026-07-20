"""
Unit tests for Pipecat voice processors.

All pipecat imports are mocked so this runs without pipecat installed.
Run with:
    python -m pytest tests/services/voice/test_pipecat_processors.py -v --noconftest
"""
import os
import sys
import types
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call as mock_call

import pytest

# ── Bypass app.services.voice.__init__ (pulls in google/anthropic/aiohttp) ───
# Register a stub package that exposes __path__ so Python can still find
# submodules (pipecat/*) but never executes the heavy __init__.py.
_VOICE_PKG_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "../../../app/services/voice")
)
_voice_stub = types.ModuleType("app.services.voice")
_voice_stub.__path__ = [_VOICE_PKG_PATH]
_voice_stub.__package__ = "app.services.voice"
sys.modules.setdefault("app.services.voice", _voice_stub)

# ── Stub app.services.chat.orchestrator so CRMLLMProcessor tests can patch it ─
_orch_stub = types.ModuleType("app.services.chat.orchestrator")
_mock_orchestrator_cls = MagicMock()
_orch_stub.ChatOrchestratorService = _mock_orchestrator_cls
sys.modules.setdefault("app.services.chat", types.ModuleType("app.services.chat"))
sys.modules.setdefault("app.services.chat.orchestrator", _orch_stub)

# ── Mock pipecat before importing any processor ───────────────────────────────

class _FP:
    """Minimal FrameProcessor mock with async hooks."""
    async def process_frame(self, frame, direction): pass
    async def push_frame(self, frame, direction=None): pass


class _TextFrame:
    def __init__(self, text=""):
        self.text = text


class _TranscriptionFrame:
    def __init__(self, text="", confidence=None):
        self.text = text
        self.confidence = confidence


class _Frame: pass


class _InterimTranscriptionFrame(_TranscriptionFrame): pass


class _TTSTextFrame(_TextFrame): pass


class _AggregatedTextFrame(_TextFrame): pass


class _LLMFullResponseStartFrame(_Frame): pass


class _LLMFullResponseEndFrame(_Frame): pass


_frames_mod = MagicMock()
_frames_mod.Frame = _Frame
_frames_mod.TextFrame = _TextFrame
_frames_mod.TranscriptionFrame = _TranscriptionFrame
_frames_mod.InterimTranscriptionFrame = _InterimTranscriptionFrame
_frames_mod.TTSTextFrame = _TTSTextFrame
_frames_mod.AggregatedTextFrame = _AggregatedTextFrame
_frames_mod.LLMFullResponseStartFrame = _LLMFullResponseStartFrame
_frames_mod.LLMFullResponseEndFrame = _LLMFullResponseEndFrame

_proc_mod = MagicMock()
_proc_mod.FrameProcessor = _FP
_proc_mod.FrameDirection = None

sys.modules.setdefault("pipecat", MagicMock())
sys.modules.setdefault("pipecat.frames", MagicMock())
sys.modules["pipecat.frames.frames"] = _frames_mod
sys.modules.setdefault("pipecat.processors", MagicMock())
sys.modules["pipecat.processors.frame_processor"] = _proc_mod


# ── Import processors after mocks are in place ────────────────────────────────

from app.services.voice.pipecat.processors.emotion_tagger import EmotionTagger  # noqa: E402
from app.services.voice.pipecat.processors.transcript_saver import TranscriptSaver, _strip_emotion_tag  # noqa: E402
from app.services.voice.pipecat.processors.crm_llm_processor import CRMLLMProcessor  # noqa: E402
from app.services.voice.pipecat.processors.note_taker import NoteTaker  # noqa: E402
from app.services.voice.pipecat.processors.handoff_monitor import HandoffMonitor  # noqa: E402
from app.services.voice.pipecat.processors.coaching_advisor import CoachingAdvisor  # noqa: E402


# ── Helpers ───────────────────────────────────────────────────────────────────

def run(coro):
    return asyncio.run(coro)


def make_text_frame(text, metadata=None):
    f = _TextFrame(text=text)
    if metadata:
        f._crm_metadata = metadata
    return f


def make_transcription_frame(text, confidence=None):
    return _TranscriptionFrame(text=text, confidence=confidence)


# ── EmotionTagger ─────────────────────────────────────────────────────────────

class TestEmotionTagger:

    def _tagger(self, tts_provider="fish_audio"):
        t = EmotionTagger.__new__(EmotionTagger)
        t._broker_id = 1
        t._tts_provider = tts_provider
        t._last_sentiment = None
        t._emotion_enabled = True
        t._response_tagged = False
        t.push_frame = AsyncMock()
        return t

    def test_injects_tag_for_fish_audio(self):
        tagger = self._tagger("fish_audio")
        frame = make_text_frame("Hola Juan")
        run(tagger.process_frame(frame, None))
        pushed = tagger.push_frame.call_args[0][0]
        assert pushed.text.startswith("[")
        assert "] Hola Juan" in pushed.text

    def test_skips_tag_for_elevenlabs(self):
        tagger = self._tagger("elevenlabs")
        frame = make_text_frame("Hola Juan")
        run(tagger.process_frame(frame, None))
        pushed = tagger.push_frame.call_args[0][0]
        assert pushed.text == "Hola Juan"

    def test_skips_if_already_tagged(self):
        tagger = self._tagger("fish_audio")
        frame = make_text_frame("[already tagged] text")
        run(tagger.process_frame(frame, None))
        pushed = tagger.push_frame.call_args[0][0]
        assert pushed.text == "[already tagged] text"

    def test_passes_non_text_frame_unchanged(self):
        tagger = self._tagger("fish_audio")
        frame = _Frame()
        run(tagger.process_frame(frame, None))
        tagger.push_frame.assert_called_once_with(frame, None)

    def test_frustrated_sentiment_uses_empathetic_tag(self):
        tagger = self._tagger("fish_audio")
        tagger._last_sentiment = "frustrated"
        frame = make_text_frame("Entiendo tu situación")
        run(tagger.process_frame(frame, None))
        pushed = tagger.push_frame.call_args[0][0]
        assert "empathetic" in pushed.text

    def test_update_sentiment(self):
        tagger = self._tagger("fish_audio")
        tagger.update_sentiment("negative")
        assert tagger._last_sentiment == "negative"

    def test_goodbye_keyword_uses_warm_tag(self):
        tagger = self._tagger("fish_audio")
        frame = make_text_frame("Hasta luego, fue un placer")
        run(tagger.process_frame(frame, None))
        pushed = tagger.push_frame.call_args[0][0]
        assert "warm" in pushed.text


# ── TranscriptSaver ───────────────────────────────────────────────────────────

class TestStripEmotionTag:
    def test_strips_tag(self):
        clean, tag = _strip_emotion_tag("[warm and friendly] Hello")
        assert clean == "Hello"
        assert tag == "warm and friendly"

    def test_no_tag(self):
        clean, tag = _strip_emotion_tag("Hello there")
        assert clean == "Hello there"
        assert tag is None

    def test_empty_string(self):
        clean, tag = _strip_emotion_tag("")
        assert clean == ""
        assert tag is None


class TestTranscriptSaver:

    def _saver(self, speaker_mode="lead"):
        s = TranscriptSaver.__new__(TranscriptSaver)
        s._voice_call_id = 42
        s._broker_id = 1
        s._speaker_mode = speaker_mode
        s._db_factory = None
        from datetime import datetime, timezone
        s._call_start = datetime.now(timezone.utc)
        s._ai_response_buffer = []
        s._ai_response_emotion = None
        s._ai_response_active = False
        s.push_frame = AsyncMock()
        s._save_line = AsyncMock()
        return s

    def test_lead_mode_saves_transcription_frame(self):
        saver = self._saver("lead")
        frame = make_transcription_frame("quiero un depa", confidence=0.95)
        run(saver.process_frame(frame, None))
        saver._save_line.assert_called_once()
        args = saver._save_line.call_args
        assert args.kwargs["text"] == "quiero un depa"
        assert args.kwargs["speaker"] == "lead"

    def test_lead_mode_skips_empty_text(self):
        saver = self._saver("lead")
        frame = make_transcription_frame("   ")
        run(saver.process_frame(frame, None))
        saver._save_line.assert_not_called()

    def test_ai_mode_saves_text_frame_stripped(self):
        saver = self._saver("ai")
        frame = make_text_frame("[enthusiastic] Encontré opciones geniales")
        run(saver.process_frame(frame, None))
        saver._save_line.assert_called_once()
        args = saver._save_line.call_args
        assert args.kwargs["text"] == "Encontré opciones geniales"
        assert args.kwargs["emotion_tag_used"] == "enthusiastic"

    def test_lead_mode_ignores_text_frame(self):
        saver = self._saver("lead")
        frame = make_text_frame("IA response")
        run(saver.process_frame(frame, None))
        saver._save_line.assert_not_called()

    def test_ai_mode_ignores_transcription_frame(self):
        saver = self._saver("ai")
        frame = make_transcription_frame("lead said something")
        run(saver.process_frame(frame, None))
        saver._save_line.assert_not_called()

    def test_always_pushes_frame(self):
        saver = self._saver("lead")
        frame = make_transcription_frame("hola")
        run(saver.process_frame(frame, None))
        saver.push_frame.assert_called_once_with(frame, None)


# ── CRMLLMProcessor ───────────────────────────────────────────────────────────

class TestCRMLLMProcessor:

    def _processor(self):
        p = CRMLLMProcessor.__new__(CRMLLMProcessor)
        p._lead_id = 1
        p._broker_id = 1
        p._voice_call_id = 42
        p._db_factory = AsyncMock()
        p._pipeline_manager = None
        p._handoff_monitor = None
        p._emotion_tagger = None
        p._call_purpose = None
        p._last_agent_type = None
        # Turn-coalescing debouncer state (normally set in __init__)
        p._coalesce_ms = 0
        p._pending_text = []
        p._pending_task = None
        p._pending_lock = asyncio.Lock()
        p._turn_in_progress = False
        p.push_frame = AsyncMock()
        return p

    @staticmethod
    def _run_frame(proc, frame):
        """process_frame + await the debounced turn task (coalesce=0)."""
        async def _go():
            await proc.process_frame(frame, None)
            if proc._pending_task is not None:
                await proc._pending_task
        asyncio.run(_go())

    def test_ignores_non_transcription_frame(self):
        proc = self._processor()
        frame = make_text_frame("some text")
        self._run_frame(proc, frame)
        proc.push_frame.assert_called_once_with(frame, None)

    def test_skips_empty_transcription(self):
        proc = self._processor()
        frame = make_transcription_frame("   ")
        self._run_frame(proc, frame)
        proc.push_frame.assert_not_called()

    def _mock_db(self):
        mock_db = MagicMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)
        return mock_db

    def test_calls_process_for_voice_and_pushes_response(self):
        proc = self._processor()
        mock_result = MagicMock()
        mock_result.response = "Hola, soy Sofía"
        mock_result.metadata = {"agent_type": "qualifier"}

        _mock_orchestrator_cls.process_for_voice = AsyncMock(return_value=mock_result)
        proc._db_factory = MagicMock(return_value=self._mock_db())

        frame = make_transcription_frame("hola busco un depa")
        self._run_frame(proc, frame)

        assert proc.push_frame.called
        pushed_texts = [
            c.args[0].text for c in proc.push_frame.call_args_list
            if hasattr(c.args[0], "text")
        ]
        assert "Hola, soy Sofía" in " ".join(pushed_texts)

    def test_forwards_call_purpose_to_orchestrator(self):
        proc = self._processor()
        proc._call_purpose = "confirmacion_visita"
        mock_result = MagicMock()
        mock_result.response = "Perfecto, confirmado"
        mock_result.metadata = {}

        _mock_orchestrator_cls.process_for_voice = AsyncMock(return_value=mock_result)
        proc._db_factory = MagicMock(return_value=self._mock_db())

        frame = make_transcription_frame("si me acomoda")
        self._run_frame(proc, frame)

        kwargs = _mock_orchestrator_cls.process_for_voice.call_args.kwargs
        assert kwargs["call_purpose"] == "confirmacion_visita"

    def test_fallback_response_on_error(self):
        proc = self._processor()
        _mock_orchestrator_cls.process_for_voice = AsyncMock(side_effect=Exception("LLM timeout"))
        proc._db_factory = MagicMock(return_value=self._mock_db())

        frame = make_transcription_frame("hola")
        self._run_frame(proc, frame)

        pushed_texts = [
            c.args[0].text for c in proc.push_frame.call_args_list
            if hasattr(c.args[0], "text")
        ]
        joined = " ".join(pushed_texts).lower()
        assert "repetir" in joined or "disculpa" in joined

    def test_suppresses_response_when_tts_muted(self):
        proc = self._processor()
        mock_manager = MagicMock()
        mock_manager.is_tts_muted.return_value = True
        proc._pipeline_manager = mock_manager

        mock_result = MagicMock()
        mock_result.response = "respuesta"
        mock_result.metadata = {}

        _mock_orchestrator_cls.process_for_voice = AsyncMock(return_value=mock_result)
        proc._db_factory = MagicMock(return_value=self._mock_db())

        frame = make_transcription_frame("algo")
        self._run_frame(proc, frame)

        proc.push_frame.assert_not_called()


# ── NoteTaker ─────────────────────────────────────────────────────────────────

class TestNoteTaker:

    def _taker(self):
        n = NoteTaker.__new__(NoteTaker)
        n._voice_call_id = 42
        n._broker_id = 1
        n._agent_user_id = None
        from collections import deque
        n._buffer = deque(maxlen=10)
        n._turn_count = 0
        n._generate_note = AsyncMock()
        n.push_frame = AsyncMock()
        return n

    def test_accumulates_lead_utterances(self):
        taker = self._taker()
        run(taker.process_frame(make_transcription_frame("hola"), None))
        run(taker.process_frame(make_transcription_frame("busco depa"), None))
        assert taker._turn_count == 2
        assert "hola" in taker._buffer
        assert "busco depa" in taker._buffer

    def test_generates_note_every_n_turns(self):
        from app.services.voice.pipecat.processors.note_taker import _NOTE_EVERY_N_TURNS
        taker = self._taker()
        for i in range(_NOTE_EVERY_N_TURNS):
            run(taker.process_frame(make_transcription_frame(f"msg {i}"), None))
        assert taker._generate_note.call_count == 1

    def test_ignores_non_transcription_frame(self):
        taker = self._taker()
        run(taker.process_frame(make_text_frame("AI response"), None))
        assert taker._turn_count == 0

    def test_skips_empty_text(self):
        taker = self._taker()
        run(taker.process_frame(make_transcription_frame("  "), None))
        assert taker._turn_count == 0

    def test_always_pushes_frame(self):
        taker = self._taker()
        frame = make_transcription_frame("algo")
        run(taker.process_frame(frame, None))
        taker.push_frame.assert_called_once_with(frame, None)


# ── HandoffMonitor ────────────────────────────────────────────────────────────

class TestHandoffMonitor:

    def _monitor(self, agent_phone="+56912345678"):
        m = HandoffMonitor.__new__(HandoffMonitor)
        m._voice_call_id = 42
        m._broker_id = 1
        m._agent_phone = agent_phone
        m._db_factory = None
        m._pipeline_manager = MagicMock()
        m._twilio_handler = None
        m._twilio_call_sid = None
        m._handoff_done = False
        m._lead_score = 0.0
        m._handoff_to_human = False
        m.push_frame = AsyncMock()
        m.trigger_handoff = AsyncMock()
        return m

    def test_triggers_on_explicit_human_request(self):
        monitor = self._monitor()
        frame = make_transcription_frame("quiero hablar con una persona")
        run(monitor.process_frame(frame, None))
        monitor.trigger_handoff.assert_called_once()

    def test_triggers_on_hot_score(self):
        monitor = self._monitor()
        monitor._lead_score = 55.0
        frame = make_transcription_frame("me interesa mucho")
        run(monitor.process_frame(frame, None))
        monitor.trigger_handoff.assert_called_once()

    def test_triggers_on_supervisor_signal(self):
        monitor = self._monitor()
        monitor._handoff_to_human = True
        frame = make_transcription_frame("ok entendí")
        run(monitor.process_frame(frame, None))
        monitor.trigger_handoff.assert_called_once()

    def test_does_not_trigger_without_signals(self):
        monitor = self._monitor()
        frame = make_transcription_frame("cuánto cuesta")
        run(monitor.process_frame(frame, None))
        monitor.trigger_handoff.assert_not_called()

    def test_skips_after_handoff_done(self):
        monitor = self._monitor()
        monitor._handoff_done = True
        monitor._handoff_to_human = True
        frame = make_transcription_frame("quiero hablar con una persona")
        run(monitor.process_frame(frame, None))
        monitor.trigger_handoff.assert_not_called()

    def test_update_from_context_sets_score(self):
        monitor = self._monitor()
        monitor.trigger_handoff = AsyncMock()
        monitor.update_from_context({"lead_score": 72.5})
        assert monitor._lead_score == 72.5

    def test_update_from_context_sets_handoff_flag(self):
        monitor = self._monitor()
        monitor.update_from_context({"handoff_to_human": True})
        assert monitor._handoff_to_human is True


# ── CoachingAdvisor ───────────────────────────────────────────────────────────

class TestCoachingAdvisor:

    def _advisor(self):
        a = CoachingAdvisor.__new__(CoachingAdvisor)
        a._voice_call_id = 42
        a._broker_id = 1
        a._agent_user_id = "99"
        from collections import deque
        a._lead_buffer = deque(maxlen=10)
        a._agent_buffer = deque(maxlen=10)
        a._turn_count = 0
        a._current_speaker = "lead"
        a._generate_suggestion = AsyncMock()
        a.push_frame = AsyncMock()
        return a

    def test_accumulates_utterances(self):
        advisor = self._advisor()
        run(advisor.process_frame(make_transcription_frame("quiero saber el precio"), None))
        assert advisor._turn_count == 1

    def test_generates_suggestion_every_n_turns(self):
        from app.services.voice.pipecat.processors.coaching_advisor import _SUGGEST_EVERY_N_TURNS
        advisor = self._advisor()
        for i in range(_SUGGEST_EVERY_N_TURNS):
            run(advisor.process_frame(make_transcription_frame(f"msg {i}"), None))
        assert advisor._generate_suggestion.call_count == 1

    def test_ignores_non_transcription_frames(self):
        advisor = self._advisor()
        run(advisor.process_frame(make_text_frame("AI says this"), None))
        assert advisor._turn_count == 0

    def test_always_pushes_frame(self):
        advisor = self._advisor()
        frame = make_transcription_frame("algo")
        run(advisor.process_frame(frame, None))
        advisor.push_frame.assert_called_once_with(frame, None)
