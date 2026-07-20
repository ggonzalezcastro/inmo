"""
Copilot pipeline — human agent calls lead; AI listens, transcribes, takes notes.

Frame flow:
    FastAPIWebsocketTransport.input()  (Twilio MediaStream)
      → DeepgramSTTService (diarized)
      → TranscriptSaver    (save all speakers)
      → NoteTaker          (periodic AI notes → WS)
    [No TTS, no audio output]

ASCII diagram:
    input → STT → TS → NoteTaker
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

try:
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.task import PipelineTask, PipelineParams
    from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport, FastAPIWebsocketParams
    from pipecat.serializers.twilio import TwilioFrameSerializer
    _PIPECAT_AVAILABLE = True
except ImportError:
    _PIPECAT_AVAILABLE = False

from app.services.voice.pipecat.processors.note_taker import NoteTaker
from app.services.voice.pipecat.processors.silero_vad_barge import build_vad_processors
from app.services.voice.pipecat.processors.transcript_saver import TranscriptSaver
from app.services.voice.pipecat.services.stt import build_deepgram_stt
from app.services.voice.pipecat.voice_config import CallSessionConfig


def build_copilot_pipeline(
    config: CallSessionConfig,
    db_session_factory: Any,
    websocket: Any,
    stream_sid: str = "",
    twilio_call_sid: str = "",
) -> "PipelineTask":
    """
    Build copilot pipeline — AI listens and takes notes, no TTS output.
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
            audio_out_enabled=False,
            add_wav_header=False,
            serializer=serializer,
        ),
    )

    vad, _ = build_vad_processors(stop_secs=0.5)  # no barge-in needed (no TTS)

    stt = build_deepgram_stt(config.voice)

    ts = TranscriptSaver(
        voice_call_id=config.voice_call_id,
        broker_id=config.broker_id,
        speaker_mode="lead",
        db_session_factory=db_session_factory,
        call_start_time=call_start,
    )

    notes = NoteTaker(
        voice_call_id=config.voice_call_id,
        broker_id=config.broker_id,
        agent_user_id=config.agent_user_id,
    )

    pipeline = Pipeline([
        transport.input(),
        vad,
        stt,
        ts,
        notes,
    ])

    return PipelineTask(
        pipeline,
        params=PipelineParams(audio_in_sample_rate=8000),
    )
