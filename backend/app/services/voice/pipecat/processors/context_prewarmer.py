"""
Context prewarmer for voice calls — eliminates first-turn cold start.

When a call starts, `prewarm_call(...)` runs in parallel with pipeline
construction:

  • DB warmup ping (`SELECT 1`) — opens a pooled connection
  • LeadContextService.get_lead_context() — fetches lead row + message_history
  • BrokerConfigService.get_config() — fetches broker config + agent persona

Results are cached in a module-level dict keyed by `voice_call_id`. The
voice orchestrator (`process_for_voice`) consumes the cache on the FIRST
turn, skipping ~3.5 s of redundant DB+context work observed in production.

The cache is one-shot — after the first turn it is dropped and subsequent
turns use the live DB session (which is fast once the pool is warm).

Controlled by env `VOICE_PREWARM_ENABLED` (default: true). Set to "0" to
disable for rollback.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PreloadedContext:
    """Cached context for the first turn of a voice call."""
    voice_call_id: int
    message_history: List[Any] = field(default_factory=list)
    broker_name: str = ""
    agent_name: str = "Sofía"
    broker_overrides: Dict[str, Any] = field(default_factory=dict)
    lead_name: str = ""
    cached_at: float = field(default_factory=time.time)


# Module-level one-shot cache
_PREWARMED: Dict[int, PreloadedContext] = {}


def is_enabled() -> bool:
    return os.getenv("VOICE_PREWARM_ENABLED", "1") not in ("0", "false", "False")


async def prewarm_call(
    voice_call_id: int,
    lead_id: int,
    broker_id: int,
) -> Optional[PreloadedContext]:
    """
    Run all expensive context fetches in parallel and cache the result.

    Safe to call multiple times — only caches once per voice_call_id.
    Returns the PreloadedContext on success, None on failure (caller should
    fall back to the slow path).
    """
    if not is_enabled():
        return None
    if voice_call_id in _PREWARMED:
        return _PREWARMED[voice_call_id]

    from app.core.database import AsyncSessionLocal
    from app.services.broker.config_service import BrokerConfigService
    from app.services.leads.context_service import LeadContextService
    from sqlalchemy import text as _sa_text

    t0 = time.perf_counter()

    async def _ping_db() -> None:
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(_sa_text("SELECT 1"))
        except Exception as e:
            logger.warning("[Prewarmer] DB ping failed call=%s: %s", voice_call_id, e)

    async def _get_history() -> List[Any]:
        try:
            async with AsyncSessionLocal() as db:
                ctx = await LeadContextService.get_lead_context(db=db, lead_id=lead_id)
                history = ctx.get("message_history", []) if isinstance(ctx, dict) else []
                return history[-2:] if len(history) > 2 else history
        except Exception as e:
            logger.warning("[Prewarmer] lead context failed call=%s: %s", voice_call_id, e)
            return []

    async def _get_broker_cfg() -> Tuple[str, str, Dict[str, Any]]:
        try:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload
            from app.models.broker import Broker
            async with AsyncSessionLocal() as db:
                # Eager-load `prompt_config` to avoid greenlet/lazy-load errors
                # when accessed after the session boundary.
                result = await db.execute(
                    select(Broker)
                    .options(selectinload(Broker.prompt_config))
                    .where(Broker.id == broker_id)
                )
                broker = result.scalars().first()
                if not broker:
                    return ("", "Sofía", {})
                prompt_cfg = getattr(broker, "prompt_config", None)
                broker_name = getattr(broker, "name", "") or ""
                agent_name = (getattr(prompt_cfg, "agent_name", None) or "Sofía") if prompt_cfg else "Sofía"
                overrides: Dict[str, Any] = {}
                if prompt_cfg is not None:
                    sp = getattr(prompt_cfg, "system_prompt", None)
                    if sp:
                        overrides["system_prompt"] = sp
                return (broker_name, agent_name, overrides)
        except Exception as e:
            logger.warning("[Prewarmer] broker config failed call=%s: %s", voice_call_id, e)
            return ("", "Sofía", {})

    async def _get_lead_name() -> str:
        try:
            from app.models.lead import Lead
            async with AsyncSessionLocal() as db:
                lead = await db.get(Lead, lead_id)
                if lead and lead.name:
                    return lead.name.strip().split()[0]
        except Exception as e:
            logger.warning("[Prewarmer] lead name fetch failed call=%s: %s", voice_call_id, e)
        return ""

    try:
        _, history, (broker_name, agent_name, broker_overrides), lead_name = await asyncio.gather(
            _ping_db(), _get_history(), _get_broker_cfg(), _get_lead_name()
        )
    except Exception as exc:
        logger.warning("[Prewarmer] gather failed call=%s: %s", voice_call_id, exc)
        return None

    preloaded = PreloadedContext(
        voice_call_id=voice_call_id,
        message_history=history,
        broker_name=broker_name,
        agent_name=agent_name,
        broker_overrides=broker_overrides,
        lead_name=lead_name,
    )
    _PREWARMED[voice_call_id] = preloaded
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "[Prewarmer] cached call=%s lead=%s broker=%s history=%d lead_name=%r elapsed=%dms",
        voice_call_id, lead_id, broker_id, len(history), lead_name, elapsed_ms,
    )
    return preloaded


def consume(voice_call_id: int) -> Optional[PreloadedContext]:
    """Pop the cached context (one-shot — only the first turn uses it)."""
    return _PREWARMED.pop(voice_call_id, None)


def cleanup(voice_call_id: int) -> None:
    """Drop cached context when a call ends (best-effort)."""
    _PREWARMED.pop(voice_call_id, None)


async def _llm_warmup_ping(voice_call_id: int) -> None:
    """Fire a 1-token LLM request to warm up OpenRouter routing + provider
    sticky-session for this call. Eliminates the ~1500ms cold-start penalty
    on the first user turn (research-confirmed cold-start cause).

    Best-effort; failures are logged and ignored.
    """
    if os.getenv("VOICE_LLM_WARMUP_ENABLED", "1") in ("0", "false", "False"):
        return
    try:
        t0 = time.perf_counter()
        from app.services.llm.factory import get_llm_provider

        provider = get_llm_provider()
        if not getattr(provider, "is_configured", False):
            return
        # Tiny ping — model returns 1 token; only goal is to warm
        # the OpenRouter→provider connection pool and sticky route.
        from app.services.llm.base_provider import LLMMessage, MessageRole
        messages = [LLMMessage(role=MessageRole.USER, content="ok")]
        try:
            await provider.generate_with_messages(messages)
        except TypeError:
            # Some providers may not accept this call shape.
            return
        except Exception as _e:
            logger.debug("[LLM-Warmup] provider call failed call=%s: %s", voice_call_id, _e)
            return
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "[LLM-Warmup] ping call=%s elapsed=%dms",
            voice_call_id, elapsed_ms,
        )
    except Exception as exc:
        logger.debug("[LLM-Warmup] ping failed call=%s: %s", voice_call_id, exc)


def schedule(voice_call_id: int, lead_id: int, broker_id: int) -> Optional[asyncio.Task]:
    """
    Fire-and-forget scheduler — kicks off prewarm in the background.

    Use this from the pipeline launcher so prewarming runs in parallel with
    Pipecat pipeline construction and the 1-second greeting delay. Also
    fires an LLM warmup ping in parallel to eliminate cold-start latency
    on the user's first turn.
    """
    if not is_enabled():
        return None
    try:
        # Fire LLM warmup in parallel (best-effort, no error if it fails).
        asyncio.create_task(_llm_warmup_ping(voice_call_id))
        return asyncio.create_task(prewarm_call(voice_call_id, lead_id, broker_id))
    except RuntimeError:
        return None
