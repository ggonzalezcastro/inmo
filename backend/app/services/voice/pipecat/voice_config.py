"""Voice configuration per broker — TTS/STT providers, voice IDs, languages, etc."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class VoiceConfig:
    """Runtime config for a single voice call session."""
    # TTS provider: "fish_audio" | "elevenlabs" | "deepgram"
    tts_provider: str = field(default_factory=lambda: os.getenv("TTS_PROVIDER", "elevenlabs"))
    # Fish Audio
    voice_id: str = field(default_factory=lambda: os.getenv("FISH_AUDIO_VOICE_ID", ""))
    model: str = field(default_factory=lambda: os.getenv("FISH_AUDIO_MODEL", "s2-pro"))
    # ElevenLabs
    elevenlabs_voice_id: str = field(default_factory=lambda: os.getenv("ELEVENLABS_VOICE_ID", ""))
    elevenlabs_model: str = field(default_factory=lambda: os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5"))
    # Deepgram TTS (aura-2 models — e.g. aura-2-thalia-en, aura-2-luna-en)
    deepgram_voice: str = field(default_factory=lambda: os.getenv("DEEPGRAM_TTS_VOICE", "aura-2-thalia-en"))
    # STT
    language: str = "es"
    stt_model: str = "nova-3"
    stt_language: str = "es-419"  # Latin American Spanish
    pipecat_log_level: str = field(default_factory=lambda: os.getenv("PIPECAT_LOG_LEVEL", "INFO"))


@dataclass
class CallSessionConfig:
    """Full config for a voice call session."""
    lead_id: int
    broker_id: int
    voice_call_id: int
    pipecat_mode: str  # "autonomous" | "copilot" | "handoff" | "coaching"
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    # For copilot / coaching / handoff modes — the human agent's user_id
    agent_user_id: Optional[int] = None
    agent_phone: Optional[str] = None
    # CallPurpose value — objective injected into the voice agent prompt
    call_purpose: Optional[str] = None


def build_tts_service(voice: VoiceConfig) -> Any:
    """
    Backwards-compat shim — delegates to `app.services.voice.pipecat.services.tts`.

    Kept here so existing pipeline modules that import
    `from ..voice_config import build_tts_service` keep working without
    rewrites. New code should import directly from the services package.
    """
    from app.services.voice.pipecat.services.tts import build_tts_service as _impl
    return _impl(voice)
