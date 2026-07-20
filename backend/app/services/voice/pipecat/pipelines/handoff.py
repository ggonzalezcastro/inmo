"""
Handoff pipeline — starts as autonomous; transfers to human when triggered.

Frame flow:
    FastAPIWebsocketTransport.input()  (Twilio MediaStream)
      → DeepgramSTTService
      → TranscriptSaver(lead)
      → CRMLLMProcessor
      → HandoffMonitor        ← intercepts handoff signals
      → EmotionTagger
      → TranscriptSaver(ai)
      → TTS
      → FastAPIWebsocketTransport.output()

When HandoffMonitor fires:
    - AI says transition message
    - Twilio SIP REFER transfers call to agent
    - TTS gets muted (pipeline continues but AI is silent)
    - VoiceCall.handoff_occurred = True

ASCII diagram:
    input → STT → TS_lead → CRM → HM → EmotionTag → TS_ai → TTS → output
                                   ↓
                              [handoff triggers mute+transfer]
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.task import PipelineTask, PipelineParams
    from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport, FastAPIWebsocketParams
    from pipecat.serializers.twilio import TwilioFrameSerializer
    _PIPECAT_AVAILABLE = True
except ImportError:
    _PIPECAT_AVAILABLE = False

from app.services.voice.pipecat.observers.latency import build_latency_observer
from app.services.voice.pipecat.processors.crm_llm_processor import CRMLLMProcessor
from app.services.voice.pipecat.processors.smart_turn import build_smart_turn
from app.services.voice.pipecat.processors.emotion_tagger import EmotionTagger
from app.services.voice.pipecat.processors.filler_player import build_filler_player  # noqa: F401
from app.services.voice.pipecat.processors.handoff_monitor import HandoffMonitor
from app.services.voice.pipecat.processors.silero_vad_barge import build_vad_processors
from app.services.voice.pipecat.processors.transcript_saver import TranscriptSaver
from app.services.voice.pipecat.services.stt import build_deepgram_stt
from app.services.voice.pipecat.services.tts import build_tts_service
from app.services.voice.pipecat.voice_config import CallSessionConfig


def build_handoff_pipeline(
    config: CallSessionConfig,
    db_session_factory: Any,
    pipeline_manager: Any,
    websocket: Any,
    stream_sid: str = "",
    twilio_call_sid: Optional[str] = None,
    twilio_handler: Optional[Any] = None,
) -> "PipelineTask":
    """
    Build handoff pipeline — autonomous AI with automatic transfer capability.
    """
    if not _PIPECAT_AVAILABLE:
        raise ImportError("pipecat-ai is not installed.")

    call_start = datetime.now(timezone.utc)

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

    vad, barger = build_vad_processors(stop_secs=0.5)

    stt = build_deepgram_stt(config.voice)

    crm = CRMLLMProcessor(
        lead_id=config.lead_id,
        broker_id=config.broker_id,
        voice_call_id=config.voice_call_id,
        db_session_factory=db_session_factory,
        pipeline_manager=pipeline_manager,
        call_purpose=config.call_purpose,
    )

    hm = HandoffMonitor(
        voice_call_id=config.voice_call_id,
        broker_id=config.broker_id,
        agent_phone=config.agent_phone,
        db_session_factory=db_session_factory,
        pipeline_manager=pipeline_manager,
        twilio_handler=twilio_handler,
        twilio_call_sid=twilio_call_sid,
    )

    crm._handoff_monitor = hm

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

    emotion = EmotionTagger(broker_id=config.broker_id, tts_provider=config.voice.tts_provider)
    tts = build_tts_service(config.voice)

    pipeline = Pipeline([
        transport.input(),
        vad,
        barger,
        *(p for p in [build_smart_turn(sample_rate=8000)] if p is not None),
        stt,
        ts_lead,
        crm,
        hm,
        emotion,
        ts_ai,
        tts,
        transport.output(),
    ])

    return PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
        ),
        observers=[o for o in [build_latency_observer(config.voice_call_id)] if o],
    )
