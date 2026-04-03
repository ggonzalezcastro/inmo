"""
Sentiment analysis Celery task — analyzes lead frustration in background.

Dispatched by the chat orchestrator after each inbound message.
Does NOT block the AI response pipeline.

Flow:
    1. Load lead + recent message history from DB
    2. Heuristic analysis (fast, no LLM)
    3. LLM confirmation if: sarcasm detected OR confidence < threshold
    4. Update sliding-window score in lead_metadata['sentiment']
    5. Determine action level (NONE / ADAPT_TONE / ESCALATE)
    6. Apply action (tone_hint injection or human_mode + WS broadcast)

NOTE: The DB engine is created INSIDE the async function (not at module level)
to avoid asyncio event-loop conflicts with Celery's forked worker processes.
"""
from __future__ import annotations

import asyncio
import logging

from celery import shared_task

from app.config import settings
from app.tasks.base import DLQTask

logger = logging.getLogger(__name__)


@shared_task(
    name="app.tasks.sentiment_tasks.analyze_sentiment",
    base=DLQTask,
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    ignore_result=True,   # fire-and-forget — no result backend needed
)
def analyze_sentiment(
    self,
    lead_id: int,
    message: str,
    broker_id: int,
    channel: str = "webchat",
) -> None:
    """Analyze sentiment of a single inbound message for the given lead."""
    if not settings.SENTIMENT_ANALYSIS_ENABLED:
        return

    # Create a fresh event loop — avoids "attached to different loop" errors
    # from asyncpg connections shared across forked Celery workers.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    exc_to_retry = None
    try:
        loop.run_until_complete(_async_analyze(lead_id, message, broker_id, channel))
    except Exception as exc:
        logger.error(
            "sentiment_task_error lead_id=%s: %s",
            lead_id, exc,
            extra={"lead_id": lead_id},
        )
        exc_to_retry = exc
    finally:
        # Always close the loop — even if self.retry() needs to be raised
        loop.close()

    if exc_to_retry:
        raise self.retry(exc=exc_to_retry)


async def _async_analyze(
    lead_id: int,
    message: str,
    broker_id: int,
    channel: str,
) -> None:
    # NOTE: All service imports are intentionally inside this async function.
    # Celery workers are forked processes — importing asyncpg at module level
    # would inherit an event loop from the parent, causing "attached to a
    # different loop" errors. Imports here ensure fresh state per task invocation.
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.future import select
    from sqlalchemy.pool import NullPool
    from app.models.lead import Lead
    from app.services.sentiment.escalation import apply_escalation_action
    from app.services.sentiment.heuristics import analyze_heuristics
    from app.services.sentiment.llm_analyzer import confirm_with_llm
    from app.services.sentiment.scorer import (
        compute_action_level,
        empty_sentiment,
        update_sentiment_window,
    )

    # NullPool: no connection pooling — each task gets a fresh connection and
    # closes it when done. Avoids pool exhaustion under concurrent load.
    engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with AsyncSessionLocal() as db:
            # SELECT FOR UPDATE (no skip_locked): serializes concurrent tasks on the
            # same lead. The wait is brief (single short transaction) and ensures
            # every message's sentiment data is captured — not silently discarded.
            result = await db.execute(
                select(Lead).where(Lead.id == lead_id).with_for_update()
            )
            lead = result.scalar_one_or_none()
            if not lead:
                logger.debug("sentiment_task: lead %s not found", lead_id)
                return

            meta = dict(lead.lead_metadata or {})

            # Skip if already escalated (human has taken over)
            current_sentiment = meta.get("sentiment", empty_sentiment())
            if current_sentiment.get("escalated", False) or lead.human_mode:
                logger.debug("sentiment_task: lead %s already escalated or in human_mode", lead_id)
                return

            # ── 2. Heuristic analysis ─────────────────────────────────────────────
            heuristic = analyze_heuristics(message)

            logger.info(
                "sentiment_heuristic lead_id=%s score=%.2f emotions=%s confidence=%.2f needs_llm=%s",
                lead_id, heuristic.score, heuristic.emotions, heuristic.confidence, heuristic.needs_llm,
            )

            # ── 3. LLM confirmation if needed ─────────────────────────────────────
            final_result = heuristic
            llm_threshold = float(getattr(settings, "SENTIMENT_LLM_CONFIRM_THRESHOLD", 0.60))

            if heuristic.score < 0.05 and not heuristic.needs_llm:
                pass  # Clearly neutral — skip LLM
            elif heuristic.needs_llm or heuristic.confidence < llm_threshold:
                context_messages = _extract_recent_context(meta)
                final_result = await confirm_with_llm(
                    message=message,
                    context_messages=context_messages,
                    heuristic_result=heuristic,
                    broker_id=broker_id,
                    lead_id=lead_id,
                )
                logger.info(
                    "sentiment_llm_used lead_id=%s score_before=%.2f score_after=%.2f emotions=%s",
                    lead_id, heuristic.score, final_result.score, final_result.emotions,
                )

            # ── 4. Update sliding window ──────────────────────────────────────────
            updated_sentiment = update_sentiment_window(
                current_sentiment=current_sentiment,
                new_score=final_result.score,
                new_emotions=final_result.emotions,
            )

            # ── 5. Determine action ───────────────────────────────────────────────
            action = compute_action_level(updated_sentiment)

            logger.info(
                "sentiment_action lead_id=%s frustration_score=%.2f action=%s",
                lead_id, updated_sentiment["frustration_score"], action.value,
            )

            # ── 6. Apply action ───────────────────────────────────────────────────
            await apply_escalation_action(
                db=db,
                lead_id=lead_id,
                broker_id=broker_id,
                action=action,
                sentiment=updated_sentiment,
                last_message=message,
                channel=channel,
            )
    finally:
        await engine.dispose()


def _extract_recent_context(meta: dict) -> list[str]:
    """Extract last 3 messages from lead_metadata for LLM context."""
    history = meta.get("message_history", [])
    context = []
    for entry in history[-4:-1]:
        role = entry.get("role", "")
        content = entry.get("content", "")
        if role and content:
            label = "Cliente" if role == "user" else "Agente"
            context.append(f"{label}: {content[:200]}")
    return context
