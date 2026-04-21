"""
AgentEventLogger — centralized fire-and-forget event logger for the multi-agent system.

All agent pipeline actions (LLM calls, handoffs, tool use, escalations, stage changes)
are recorded here for the observability dashboard, conversation debugger, and cost analytics.

Design principles:
- Fire-and-forget: log calls never block the chat response path
- Async-safe: can be called from any async context
- Fail-soft: logging errors are caught and never propagate to the caller
- Idempotent: duplicate events are safe (may occur during retries)

Usage:
    from app.services.observability.event_logger import event_logger

    await event_logger.log_llm_call(
        lead_id=42, broker_id=5,
        provider="gemini", model="gemini-2.5-flash",
        input_tokens=1200, output_tokens=89,
        latency_ms=1340, cost_usd=0.0018,
        agent_type="qualifier",
    )
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentEventLogger:
    """
    Singleton event logger for the multi-agent system.

    Writes `agent_events` rows asynchronously without blocking callers.
    Errors are swallowed so observability never degrades the AI pipeline.
    """

    # ── Public log methods ────────────────────────────────────────────────────

    async def log_agent_selected(
        self,
        lead_id: int,
        broker_id: int,
        agent_type: str,
        reason: str,
        message_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> None:
        await self._log(
            event_type="agent_selected",
            lead_id=lead_id,
            broker_id=broker_id,
            agent_type=agent_type,
            message_id=message_id,
            conversation_id=conversation_id,
            event_metadata={"reason": reason},
        )

    async def log_handoff(
        self,
        lead_id: int,
        broker_id: int,
        from_agent: str,
        to_agent: str,
        reason: str,
        message_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> None:
        await self._log(
            event_type="agent_handoff",
            lead_id=lead_id,
            broker_id=broker_id,
            from_agent=from_agent,
            to_agent=to_agent,
            handoff_reason=reason,
            message_id=message_id,
            conversation_id=conversation_id,
        )

    async def log_llm_call(
        self,
        lead_id: int,
        broker_id: int,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        cost_usd: float,
        agent_type: Optional[str] = None,
        message_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
        system_prompt: Optional[str] = None,       # hashed; raw only stored in debug mode
        raw_response_snippet: Optional[str] = None,  # first 500 chars of response
        user_messages: Optional[List[Dict]] = None,  # messages sent to LLM (stored in metadata)
        rag_chunks_used: Optional[List] = None,       # KB chunk IDs used (stored in metadata)
        temperature: Optional[float] = None,
        thinking_content: Optional[str] = None,       # model's internal reasoning text
    ) -> None:
        prompt_hash = None
        if system_prompt:
            prompt_hash = hashlib.sha256(system_prompt.encode()).hexdigest()

        extra_meta: Dict[str, Any] = {}
        if user_messages:
            # Store truncated messages (cap each at 300 chars to avoid DB bloat)
            extra_meta["user_messages"] = [
                {**m, "content": str(m.get("content", ""))[:300]} for m in (user_messages[:20])
            ]
        if rag_chunks_used:
            extra_meta["rag_chunks_used"] = rag_chunks_used[:10]
        if temperature is not None:
            extra_meta["temperature"] = temperature
        if thinking_content:
            # Store up to 2000 chars to avoid DB bloat; models can think extensively
            extra_meta["thinking_content"] = thinking_content[:2000]

        await self._log(
            event_type="llm_call",
            lead_id=lead_id,
            broker_id=broker_id,
            agent_type=agent_type,
            message_id=message_id,
            conversation_id=conversation_id,
            llm_provider=provider,
            llm_model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            llm_latency_ms=latency_ms,
            llm_cost_usd=cost_usd,
            system_prompt_hash=prompt_hash,
            raw_response_snippet=(raw_response_snippet or "")[:500] if raw_response_snippet else None,
            event_metadata=extra_meta or None,
        )

    async def log_tool_call(
        self,
        lead_id: int,
        broker_id: int,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
        latency_ms: int,
        success: bool,
        agent_type: Optional[str] = None,
        message_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> None:
        # Truncate large outputs to avoid bloating the DB
        output_stored = tool_output
        if isinstance(output_stored, list) and len(output_stored) > 5:
            output_stored = output_stored[:5] + [{"_truncated": len(output_stored) - 5}]

        await self._log(
            event_type="tool_called",
            lead_id=lead_id,
            broker_id=broker_id,
            agent_type=agent_type,
            message_id=message_id,
            conversation_id=conversation_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=output_stored if isinstance(output_stored, dict) else {"result": str(output_stored)[:500]},
            tool_latency_ms=latency_ms,
            tool_success=success,
        )

    async def log_stage_change(
        self,
        lead_id: int,
        broker_id: int,
        stage_before: str,
        stage_after: str,
        score_before: float,
        score_after: float,
        message_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> None:
        await self._log(
            event_type="pipeline_stage_changed",
            lead_id=lead_id,
            broker_id=broker_id,
            pipeline_stage_before=stage_before,
            pipeline_stage_after=stage_after,
            lead_score_before=score_before,
            lead_score_after=score_after,
            score_delta=score_after - score_before,
            message_id=message_id,
            conversation_id=conversation_id,
        )

    async def log_escalation(
        self,
        lead_id: int,
        broker_id: int,
        reason: str,
        frustration_score: Optional[float] = None,
        message_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> None:
        await self._log(
            event_type="escalation_triggered",
            lead_id=lead_id,
            broker_id=broker_id,
            message_id=message_id,
            conversation_id=conversation_id,
            event_metadata={
                "reason": reason,
                "frustration_score": frustration_score,
            },
        )

    async def log_human_takeover(
        self,
        lead_id: int,
        broker_id: int,
        agent_id: int,
        message_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> None:
        await self._log(
            event_type="human_takeover",
            lead_id=lead_id,
            broker_id=broker_id,
            message_id=message_id,
            conversation_id=conversation_id,
            event_metadata={"human_agent_id": agent_id},
        )

    async def log_human_release(
        self,
        lead_id: int,
        broker_id: int,
        agent_id: int,
        note: Optional[str] = None,
        message_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> None:
        await self._log(
            event_type="human_release",
            lead_id=lead_id,
            broker_id=broker_id,
            message_id=message_id,
            conversation_id=conversation_id,
            event_metadata={"human_agent_id": agent_id, "note_length": len(note or "")},
        )

    async def log_qualification(
        self,
        lead_id: int,
        broker_id: int,
        extracted_fields: Dict[str, Any],
        score_delta: float,
        agent_type: str = "qualifier",
        message_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> None:
        await self._log(
            event_type="qualification_analysis",
            lead_id=lead_id,
            broker_id=broker_id,
            agent_type=agent_type,
            message_id=message_id,
            conversation_id=conversation_id,
            extracted_fields=extracted_fields,
            score_delta=score_delta,
        )

    async def log_property_search(
        self,
        lead_id: int,
        broker_id: int,
        search_params: Dict[str, Any],
        strategy: str,
        results_count: int,
        top_result_ids: Optional[List[int]] = None,
        rrf_scores: Optional[Dict] = None,
        embedding_tokens: int = 0,
        embedding_cost_usd: float = 0.0,
        latency_ms: Optional[int] = None,
        message_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> None:
        await self._log(
            event_type="property_search",
            lead_id=lead_id,
            broker_id=broker_id,
            agent_type="property",
            message_id=message_id,
            conversation_id=conversation_id,
            search_strategy=strategy,
            search_results_count=results_count,
            tool_latency_ms=latency_ms,
            event_metadata={
                "search_params": search_params,
                "top_result_ids": top_result_ids or [],
                "rrf_scores": rrf_scores or {},
                "embedding_tokens": embedding_tokens,
                "embedding_cost_usd": embedding_cost_usd,
            },
        )

    async def log_error(
        self,
        lead_id: int,
        broker_id: int,
        error_type: str,
        error_message: str,
        error_stack: Optional[str] = None,
        agent_type: Optional[str] = None,
        message_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> None:
        await self._log(
            event_type="error",
            lead_id=lead_id,
            broker_id=broker_id,
            agent_type=agent_type,
            message_id=message_id,
            conversation_id=conversation_id,
            error_type=error_type,
            error_message=error_message,
            error_stack=error_stack,
        )

    async def log_fallback_triggered(
        self,
        lead_id: int,
        broker_id: int,
        primary_provider: str,
        fallback_provider: str,
        error_reason: str,
        agent_type: Optional[str] = None,
    ) -> None:
        await self._log(
            event_type="fallback_triggered",
            lead_id=lead_id,
            broker_id=broker_id,
            agent_type=agent_type,
            llm_provider=primary_provider,
            event_metadata={
                "fallback_provider": fallback_provider,
                "error_reason": error_reason,
            },
        )

    async def log_sentiment_analyzed(
        self,
        lead_id: int,
        broker_id: int,
        frustration_score: float,
        action_level: str,
        tone_hint: Optional[str] = None,
        emotions: Optional[List[str]] = None,
        keywords_matched: Optional[List[str]] = None,
        message_id: Optional[int] = None,
    ) -> None:
        await self._log(
            event_type="sentiment_analyzed",
            lead_id=lead_id,
            broker_id=broker_id,
            message_id=message_id,
            event_metadata={
                "frustration_score": frustration_score,
                "action_level": action_level,
                "tone_hint": tone_hint,
                "emotions": emotions or [],
                "keywords_matched": keywords_matched or [],
            },
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _log(self, event_type: str, **kwargs: Any) -> None:
        """Persist an agent event row asynchronously. Never raises."""
        asyncio.ensure_future(self._write(event_type=event_type, **kwargs))

    async def _write(self, event_type: str, **kwargs: Any) -> None:
        """Actual DB write + Redis publish — runs as a fire-and-forget task."""
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.agent_event import AgentEvent
            import json

            async with AsyncSessionLocal() as db:
                event = AgentEvent(event_type=event_type, **kwargs)
                db.add(event)
                await db.commit()
                await db.refresh(event)

            # Publish to Redis for live-tail WebSocket
            try:
                from app.core.redis_client import get_redis
                redis = await get_redis()
                broker_id = kwargs.get("broker_id")
                payload = json.dumps({
                    "event_type": event_type,
                    "agent_type": kwargs.get("agent_type"),
                    "lead_id": kwargs.get("lead_id"),
                    "broker_id": broker_id,
                    "ts": event.created_at.isoformat() if event.created_at else None,
                    "metadata": kwargs.get("event_metadata"),
                })
                channel = f"obs:live:{broker_id}" if broker_id else "obs:live:system"
                await redis.publish(channel, payload)
            except Exception as pub_exc:
                logger.debug("Live-tail publish failed: %s", pub_exc)

        except Exception as exc:
            # Never let logging errors propagate to the chat pipeline
            logger.warning("AgentEventLogger._write failed [%s]: %s", event_type, exc)


# Module-level singleton — import this everywhere
event_logger = AgentEventLogger()
