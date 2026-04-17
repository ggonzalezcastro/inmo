"""
Escalation actions triggered when frustration score crosses thresholds.

Actions:
  ADAPT_TONE → inject tone_hint into lead_metadata so agents soften their response
  ESCALATE   → set human_mode=True + broadcast lead_frustrated WebSocket event
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sentiment.scorer import ActionLevel, resolve_tone_hint

logger = logging.getLogger(__name__)


async def apply_escalation_action(
    db: AsyncSession,
    lead_id: int,
    broker_id: int,
    action: ActionLevel,
    sentiment: Dict[str, Any],
    last_message: str,
    channel: str = "webchat",
    reason: str = "frustration",
) -> None:
    """
    Apply the appropriate escalation action based on ActionLevel.

    Modifies lead_metadata in the DB atomically (only the 'sentiment' sub-key
    and 'human_mode' when escalating).
    """
    if action == ActionLevel.NONE:
        tone_hint = resolve_tone_hint(sentiment)
        if tone_hint is None and not _has_stale_tone_hint(sentiment):
            return  # Nothing to do
        # Clear stale tone_hint if score dropped below threshold
        await _update_sentiment_field(db, lead_id, sentiment, tone_hint=None)
        return

    if action == ActionLevel.ADAPT_TONE:
        tone_hint = resolve_tone_hint(sentiment)
        logger.info(
            "sentiment_tone_adapted",
            extra={"lead_id": lead_id, "broker_id": broker_id, "tone_hint": tone_hint},
        )
        await _update_sentiment_field(db, lead_id, sentiment, tone_hint=tone_hint)
        return

    if action == ActionLevel.ESCALATE:
        await _escalate(db, lead_id, broker_id, sentiment, last_message, channel, reason=reason)


def _has_stale_tone_hint(sentiment: Dict[str, Any]) -> bool:
    """True if there's a tone_hint that should be cleared."""
    return sentiment.get("tone_hint") is not None


async def _update_sentiment_field(
    db: AsyncSession,
    lead_id: int,
    sentiment: Dict[str, Any],
    tone_hint: Optional[str] = None,
) -> None:
    """Atomically update only the sentiment sub-key in lead_metadata."""
    from sqlalchemy import text

    sentiment_copy = dict(sentiment)
    sentiment_copy["tone_hint"] = tone_hint

    await db.execute(
        text("""
            UPDATE leads
            SET metadata = jsonb_set(
                COALESCE(metadata, '{}'),
                '{sentiment}',
                CAST(:sentiment_value AS jsonb),
                true
            )
            WHERE id = :lead_id
        """),
        {
            "lead_id": lead_id,
            "sentiment_value": __import__("json").dumps(sentiment_copy),
        },
    )
    await db.commit()


async def _escalate(
    db: AsyncSession,
    lead_id: int,
    broker_id: int,
    sentiment: Dict[str, Any],
    last_message: str,
    channel: str,
    reason: str = "frustration",
) -> None:
    """
    Full escalation: activate human_mode + broadcast lead_frustrated event.

    Idempotent — if already escalated, skips without DB write or WS broadcast.
    """
    # Guard: skip if this lead was already escalated (handles DLQ retries and
    # concurrent tasks that slipped past the task-level check).
    if sentiment.get("escalated"):
        logger.info("sentiment_already_escalated lead_id=%s — skipping", lead_id)
        return

    from sqlalchemy import text
    from sqlalchemy.future import select
    from app.models.lead import Lead

    # Load lead name + assigned agent for broadcast
    result = await db.execute(select(Lead.name, Lead.phone, Lead.assigned_to).where(Lead.id == lead_id))
    row = result.first()
    if row:
        lead_name = row[0] or row[1] or f"Lead {lead_id}"
        assigned_to = row[2]
    else:
        lead_name = f"Lead {lead_id}"
        assigned_to = None

    # Update sentiment + activate human_mode atomically
    sentiment_updated = dict(sentiment)
    sentiment_updated["escalated"] = True
    sentiment_updated["escalated_at"] = datetime.now(timezone.utc).isoformat()
    sentiment_updated["escalated_reason"] = reason
    sentiment_updated["tone_hint"] = None  # Clear tone_hint when escalating

    import json

    await db.execute(
        text("""
            UPDATE leads
            SET
                metadata = jsonb_set(
                    COALESCE(metadata, '{}') - 'human_mode_notified',
                    '{sentiment}',
                    CAST(:sentiment_value AS jsonb),
                    true
                ),
                human_mode = true,
                human_taken_at = NOW(),
                human_released_at = NULL,
                human_release_note = NULL
            WHERE id = :lead_id
        """),
        {
            "lead_id": lead_id,
            "sentiment_value": json.dumps(sentiment_updated),
        },
    )
    await db.commit()

    score = sentiment.get("frustration_score", 0.0)
    emotions = []
    for entry in sentiment.get("message_scores", [])[:2]:
        emotions.extend(entry.get("emotions", []))
    emotions = list(set(emotions))

    logger.warning(
        "sentiment_escalated",
        extra={
            "lead_id": lead_id,
            "broker_id": broker_id,
            "frustration_score": score,
            "emotions": emotions,
        },
    )

    # Log escalation event to agent_events
    try:
        from app.services.observability.event_logger import event_logger
        await event_logger.log_escalation(
            lead_id=lead_id,
            broker_id=broker_id,
            reason=reason,
            frustration_score=score,
        )
    except Exception as exc:
        logger.warning("Failed to log escalation event: %s", exc)

    # Generate escalation brief asynchronously (don't block WS broadcast).
    # NOTE: db.commit() already ran above, so the fresh_db session inside
    # _generate_brief_background will see committed escalation data.
    try:
        import asyncio
        asyncio.create_task(_generate_brief_background(
            lead_id=lead_id,
            broker_id=broker_id,
            reason=reason,
            frustration_score=score,
        ))
    except Exception as exc:
        logger.warning("Failed to schedule brief generation: %s", exc)

    # Broadcast to broker dashboard
    try:
        from app.core.websocket_manager import ws_manager
        await ws_manager.broadcast(
            broker_id,
            "lead_frustrated",
            {
                "lead_id": lead_id,
                "lead_name": lead_name,
                "frustration_score": round(score, 3),
                "emotions": emotions,
                "last_message": last_message[:300],
                "channel": channel,
                "assigned_to": assigned_to,
            },
        )
    except Exception as exc:
        logger.warning("sentiment_ws_broadcast_failed: %s", exc)


async def _generate_brief_background(
    lead_id: int,
    broker_id: int,
    reason: str,
    frustration_score: float,
) -> None:
    """Fire-and-forget brief generation after escalation."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.models.lead import Lead
        from sqlalchemy.future import select
        from app.services.handoff.brief_generator import generate_escalation_brief

        async with AsyncSessionLocal() as fresh_db:
            result = await fresh_db.execute(select(Lead).where(Lead.id == lead_id))
            lead = result.scalar_one_or_none()
            if lead is None:
                return

            lead_data = {
                "name": lead.name,
                "phone": lead.phone,
                "email": lead.email,
                **(lead.lead_metadata or {}),
            }

            # Fetch the last 10 messages for the brief's LLM prompt
            from app.models.chat_message import ChatMessage
            from sqlalchemy import desc
            msg_result = await fresh_db.execute(
                select(ChatMessage)
                .where(ChatMessage.lead_id == lead_id)
                .order_by(desc(ChatMessage.created_at))
                .limit(10)
            )
            recent_msgs = [
                {"role": m.direction, "content": m.message_text}
                for m in reversed(msg_result.scalars().all())
            ]

            await generate_escalation_brief(
                db=fresh_db,
                lead_id=lead_id,
                broker_id=broker_id,
                reason=reason,
                lead_data=lead_data,
                recent_messages=recent_msgs,
                frustration_score=frustration_score,
            )
            await fresh_db.commit()
    except Exception as exc:
        logger.warning("Background brief generation failed: %s", exc)
