"""
TTS factory — selects provider via env TTS_PROVIDER and applies latency-tuned settings.

Latency comparison (TTFB, observed on Pipecat 1.2 over Twilio µ-law):

    elevenlabs (eleven_flash_v2_5, auto_mode=True)  ~75 ms   ← default
    deepgram   (aura-2-*)                           ~100 ms
    fish_audio (s2-pro, latency="normal")           ~150 ms  (better prosody, slower)

Critical knobs:
- ElevenLabs `auto_mode=True` disables server-side chunk scheduling buffer
  (equivalent to optimize_streaming_latency=3 on the REST API).
- `sample_rate=8000` requests 8 kHz output → matches Twilio MediaStream µ-law
  natively and skips a transcoding step in the serializer.
- For `fish_audio` keep `latency="normal"` (higher quality) unless on very
  slow networks; `latency="low"` shaves ~50 ms but adds audible artefacts.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def build_tts_service(voice: Any) -> Any:
    """
    Return a Pipecat TTS service based on `voice.tts_provider`.

    Supported providers: "elevenlabs" (default), "deepgram", "fish_audio".
    Raises ValueError for unknown providers so the misconfig is loud and visible.
    """
    provider = (getattr(voice, "tts_provider", "elevenlabs") or "elevenlabs").lower()

    if provider == "elevenlabs":
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

        voice_id = (
            getattr(voice, "elevenlabs_voice_id", "")
            or os.getenv("ELEVENLABS_VOICE_ID", "")
            or "pNInz6obpgDQGcFmaJgB"  # premade "Adam" (Spanish-capable)
        )
        model = getattr(voice, "elevenlabs_model", None) or os.getenv(
            "ELEVENLABS_MODEL", "eleven_flash_v2_5"
        )
        logger.info("[TTS] elevenlabs model=%s voice_id=%s auto_mode=True", model, voice_id)
        return ElevenLabsTTSService(
            api_key=os.getenv("ELEVENLABS_API_KEY", ""),
            settings=ElevenLabsTTSService.Settings(voice=voice_id, model=model),
            sample_rate=8000,
            auto_mode=True,
        )

    if provider == "deepgram":
        from pipecat.services.deepgram.tts import DeepgramTTSService, DeepgramTTSSettings

        deepgram_voice = getattr(voice, "deepgram_voice", None) or os.getenv(
            "DEEPGRAM_TTS_VOICE", "aura-2-thalia-en"
        )
        logger.info("[TTS] deepgram voice=%s", deepgram_voice)
        return DeepgramTTSService(
            api_key=os.getenv("DEEPGRAM_API_KEY", ""),
            settings=DeepgramTTSSettings(voice=deepgram_voice),
            sample_rate=8000,
        )

    if provider == "fish_audio":
        from pipecat.services.fish.tts import FishAudioTTSService, FishAudioTTSSettings

        voice_id = getattr(voice, "voice_id", "") or os.getenv("FISH_AUDIO_VOICE_ID", "")
        model = getattr(voice, "model", None) or os.getenv("FISH_AUDIO_MODEL", "s1")
        # Default to "low" (TTFB ~150 ms vs ~330 ms on "balanced") for live voice
        # calls — sentence-level streaming masks the slight prosody dip and the
        # latency win materially improves perceived responsiveness.
        # Override via FISH_AUDIO_LATENCY=balanced if quality regression observed.
        fish_latency = os.getenv("FISH_AUDIO_LATENCY", "low")
        logger.info(
            "[TTS] fish_audio voice=%s model=%s latency=%s", voice_id, model, fish_latency,
        )
        return FishAudioTTSService(
            api_key=os.getenv("FISH_AUDIO_API_KEY", ""),
            settings=FishAudioTTSSettings(
                voice=voice_id,
                model=model,
                latency=fish_latency,
                temperature=0.7,
                prosody_speed=float(os.getenv("FISH_AUDIO_PROSODY_SPEED", "1.05")),
            ),
        )

    raise ValueError(
        f"Unknown TTS_PROVIDER: {provider!r}. Use 'elevenlabs', 'deepgram', or 'fish_audio'."
    )
