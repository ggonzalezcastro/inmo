"""
Autonomous pipeline — AI calls the lead and handles the full conversation.

Frame flow:
    FastAPIWebsocketTransport.input()  (Twilio MediaStream)
      → DeepgramSTTService     (speech to text)
      → TranscriptSaver(lead)  (save + WS broadcast)
      → CRMLLMProcessor        (AgentSupervisor → response)
      → EmotionTagger          (inject Fish Audio emotion tag)
      → TranscriptSaver(ai)    (save AI text + WS broadcast)
      → TTS (ElevenLabs or Fish Audio)
      → FastAPIWebsocketTransport.output()

ASCII diagram:
    input → STT → TS_lead → CRM → EmotionTag → TS_ai → TTS → output
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

try:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineTask, PipelineParams
    from pipecat.transports.websocket.fastapi import (
        FastAPIWebsocketTransport,
        FastAPIWebsocketParams,
    )
    from pipecat.serializers.twilio import TwilioFrameSerializer
    _PIPECAT_AVAILABLE = True
except ImportError:
    _PIPECAT_AVAILABLE = False

from app.services.voice.pipecat.observers.latency import build_latency_observer
from app.services.voice.pipecat.processors.crm_llm_processor import CRMLLMProcessor
from app.services.voice.pipecat.processors.smart_turn import build_smart_turn
from app.services.voice.pipecat.processors.emotion_tagger import EmotionTagger
from app.services.voice.pipecat.processors.silero_vad_barge import build_vad_processors
from app.services.voice.pipecat.processors.transcript_saver import TranscriptSaver
from app.services.voice.pipecat.services.stt import build_deepgram_stt
from app.services.voice.pipecat.services.tts import build_tts_service
from app.services.voice.pipecat.voice_config import CallSessionConfig


def build_autonomous_pipeline(
    config: CallSessionConfig,
    db_session_factory: Any,
    pipeline_manager: Any,
    websocket: Any,
    stream_sid: str = "",
    twilio_call_sid: str = "",
) -> "PipelineTask":
    """
    Build and return a Pipecat PipelineTask for autonomous mode.

    Parameters
    ----------
    config              : CallSessionConfig with lead/broker/call IDs
    db_session_factory  : async callable → AsyncSession
    pipeline_manager    : PipelineManager singleton
    websocket           : FastAPI/Starlette WebSocket object (from Twilio connection)
    stream_sid          : Twilio MediaStream SID (for hang-up support)
    """
    if not _PIPECAT_AVAILABLE:
        raise ImportError("pipecat-ai is not installed. Run: pip install 'pipecat-ai[deepgram,elevenlabs]'")

    call_start = datetime.now(timezone.utc)
    logger.info(
        "[AutonomousPipeline] building call_id=%s lead=%s broker=%s tts=%s",
        config.voice_call_id, config.lead_id, config.broker_id, config.voice.tts_provider,
    )

    # ── Transport ─────────────────────────────────────────────────────────────
    serializer = TwilioFrameSerializer(
        stream_sid=stream_sid,
        call_sid=twilio_call_sid or None,
        account_sid=os.getenv("TWILIO_ACCOUNT_SID") or None,
        auth_token=os.getenv("TWILIO_AUTH_TOKEN") or None,
        params=TwilioFrameSerializer.InputParams(
            auto_hang_up=bool(twilio_call_sid),
        ),
    )
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
        ),
    )

    # ── VAD (Silero ML) ───────────────────────────────────────────────────────
    vad, barger = build_vad_processors(stop_secs=0.5)

    # ── STT (latency-tuned: 300ms endpointing, interim results) ──────────────
    stt = build_deepgram_stt(config.voice)

    # ── CRM LLM ───────────────────────────────────────────────────────────────
    crm = CRMLLMProcessor(
        lead_id=config.lead_id,
        broker_id=config.broker_id,
        voice_call_id=config.voice_call_id,
        db_session_factory=db_session_factory,
        pipeline_manager=pipeline_manager,
        call_purpose=config.call_purpose,
    )

    # ── Transcript savers ─────────────────────────────────────────────────────
    ts_lead = TranscriptSaver(
        voice_call_id=config.voice_call_id,
        broker_id=config.broker_id,
        speaker_mode="lead",
        db_session_factory=db_session_factory,
        call_start_time=call_start,
    )
    ts_ai = TranscriptSaver(
        voice_call_id=config.voice_call_id,
        broker_id=config.broker_id,
        speaker_mode="ai",
        db_session_factory=db_session_factory,
        call_start_time=call_start,
    )

    # ── Emotion tagger ────────────────────────────────────────────────────────
    emotion = EmotionTagger(broker_id=config.broker_id, tts_provider=config.voice.tts_provider)

    # ── TTS ───────────────────────────────────────────────────────────────────
    tts = build_tts_service(config.voice)

    # ── Pipeline ──────────────────────────────────────────────────────────────
    # FillerPlayer sits between ts_lead and crm so it can emit a short
    # filler TextFrame (gets pushed to TTS) the moment a final transcript
    # arrives — masks the ~2 s LLM latency from the lead.
    pipeline = Pipeline([
        transport.input(),
        vad,
        barger,
        *(p for p in [build_smart_turn(sample_rate=8000)] if p is not None),
        stt,
        ts_lead,
        crm,
        emotion,
        ts_ai,
        tts,
        transport.output(),
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
        ),
        observers=[o for o in [build_latency_observer(config.voice_call_id)] if o],
    )
    logger.info(
        "[AutonomousPipeline] ready call_id=%s stream_sid=%s call_sid=%s auto_hang_up=%s",
        config.voice_call_id, stream_sid, twilio_call_sid, bool(twilio_call_sid),
    )
    return task
