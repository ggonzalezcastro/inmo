"""
Deepgram STT factory — latency-tuned for Spanish voice calls.

Key tunings (vs Pipecat defaults):
- endpointing=150 ms     → final transcript fires 350 ms sooner than default 500 ms
- interim_results=True   → start LLM warmup on partials (lower TTFT)
- utterance_end_ms=800   → cap max silence inside one utterance
- vad_events=True        → emit speech_started / speech_finished for tighter turn-taking
- model=nova-3           → best ES-419 accuracy available today
- smart_format/punctuate → readable transcripts for the LLM

Pause tolerance previously handled by 300 ms endpointing is now provided by the
Silero VAD processor (`build_vad_processors(stop_secs=0.5)`) upstream of STT,
which prevents premature interruptions while keeping STT responsive.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def build_deepgram_stt(voice: Any) -> Any:
    """
    Build a latency-tuned DeepgramSTTService for a voice call.

    Parameters
    ----------
    voice : VoiceConfig
        Holds `stt_model` (default 'nova-3') and `stt_language` ('es-419').
    """
    from pipecat.services.deepgram.stt import DeepgramSTTService, DeepgramSTTSettings

    model = getattr(voice, "stt_model", "nova-3")
    language = getattr(voice, "stt_language", "es-419")

    # Allow override via env without code changes (rollback).
    # NOTE: Deepgram requires utterance_end_ms >= 1000; values below silently
    # disable utterance-end events, which can starve final transcripts.
    endpointing_ms = int(os.getenv("DEEPGRAM_ENDPOINTING_MS") or "300")
    utterance_end_ms = max(1000, int(os.getenv("DEEPGRAM_UTTERANCE_END_MS") or "1000"))

    logger.info(
        "[STT] deepgram model=%s lang=%s endpointing=%dms utterance_end=%dms",
        model, language, endpointing_ms, utterance_end_ms,
    )

    # Real-estate keyterm vocabulary boost — improves recall on Chilean
    # property-domain words that Deepgram tends to mis-transcribe.
    # Comma-separated env override available via DEEPGRAM_KEYTERMS.
    default_keyterms = (
        "DICOM,UF,departamento,dividendo,pre-aprobación,subsidio,"
        "pie,bono pie,crédito hipotecario,tasación,escrituración,"
        "metraje,bodega,estacionamiento,Sofía,inmobiliaria,arriendo,"
        "subsidio DS1,subsidio DS19,renta,liquidación"
    )
    keyterms_raw = os.getenv("DEEPGRAM_KEYTERMS", default_keyterms)
    keyterms = [k.strip() for k in keyterms_raw.split(",") if k.strip()]

    settings_kwargs: dict = dict(
        model=model,
        language=language,
        smart_format=True,
        punctuate=True,
        interim_results=True,
        endpointing=endpointing_ms,
        utterance_end_ms=utterance_end_ms,
    )
    # keyterm only supported on nova-3 + en/multi; nova-3 ES-419 accepts it.
    if model.startswith("nova-3") and keyterms:
        settings_kwargs["keyterm"] = keyterms
    return DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY", ""),
        settings=DeepgramSTTSettings(**settings_kwargs),
        # Hint Pipecat's stop-strategy with our measured p99 Deepgram
        # time-to-final-speech (TTFS). Default in Pipecat is 0.45s; we run
        # closer to 0.25–0.35s on nova-3 ES-419 — letting the stop-strategy
        # commit the turn sooner. Override via DEEPGRAM_TTFS_P99 (seconds).
        ttfs_p99_latency=float(os.getenv("DEEPGRAM_TTFS_P99") or "0.30"),
    )
