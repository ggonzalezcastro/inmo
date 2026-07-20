"""Latency observer factory — wraps Pipecat's `UserBotLatencyObserver`
with structured logging for production grepping.

Docs: pipecat.observers.user_bot_latency_observer (Pipecat 1.2.1)
Requires `enable_metrics=True` in PipelineParams (already set in our pipelines).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def build_latency_observer(voice_call_id: int) -> Optional[Any]:
    """Return a configured UserBotLatencyObserver, or None if Pipecat lacks it.

    Emits three structured log lines per relevant frame, grep-friendly:

    * ``[VOICE-LATENCY-E2E]``        user-stop → bot-speak (one per turn)
    * ``[VOICE-LATENCY-BREAKDOWN]``  per-processor TTFB (one per turn)
    * ``[VOICE-LATENCY-FIRST]``      client-connect → first bot speech (once)
    """
    try:
        from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver
    except Exception as exc:
        logger.warning("[LatencyObserver] not available: %s", exc)
        return None

    obs = UserBotLatencyObserver()

    @obs.event_handler("on_latency_measured")
    async def _on_measured(_o, secs):
        try:
            logger.info(
                "[VOICE-LATENCY-E2E] call=%s user_stop_to_bot_speak_ms=%d",
                voice_call_id, int(secs * 1000),
            )
        except Exception:
            pass

    @obs.event_handler("on_latency_breakdown")
    async def _on_breakdown(_o, breakdown):
        try:
            ttfb_parts = " ".join(
                f"{getattr(m, 'processor', '?')}={int(getattr(m, 'duration_secs', 0) * 1000)}ms"
                for m in (getattr(breakdown, "ttfb", None) or [])
            )
            user_turn_ms = int((getattr(breakdown, "user_turn_secs", None) or 0) * 1000)
            agg = getattr(breakdown, "text_aggregation", None)
            agg_ms = int(getattr(agg, "duration_secs", 0) * 1000) if agg else 0
            logger.info(
                "[VOICE-LATENCY-BREAKDOWN] call=%s user_turn_ms=%d agg_ms=%d %s",
                voice_call_id, user_turn_ms, agg_ms, ttfb_parts,
            )
        except Exception as exc:
            logger.debug("[LatencyObserver] breakdown log failed: %s", exc)

    @obs.event_handler("on_first_bot_speech_latency")
    async def _on_first(_o, secs):
        try:
            logger.info(
                "[VOICE-LATENCY-FIRST] call=%s connect_to_first_speech_ms=%d",
                voice_call_id, int(secs * 1000),
            )
        except Exception:
            pass

    return obs
