"""
Human mode timeout Celery task.

Runs every 5 minutes via Beat and checks for leads that have been in human_mode
for longer than configured thresholds. Takes tiered action:

  15 min  → WebSocket reminder to the assigned agent
  30 min  → WebSocket alert to all broker connections (admin-level)
  60 min  → Auto-release: clears human_mode, resets sentiment, notifies broker

Notifications use Redis PUBLISH so they reach the API process's WebSocket
listener regardless of which worker process runs this task.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from celery import shared_task
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.future import select

from app.config import settings
from app.tasks.base import DLQTask

logger = logging.getLogger(__name__)


@shared_task(
    name="app.tasks.human_timeout_tasks.check_human_mode_timeouts",
    base=DLQTask,
    bind=True,
    max_retries=1,
    ignore_result=True,
)
def check_human_mode_timeouts(self) -> None:
    """Periodic task: check for stale human_mode leads and take tiered action."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_async_check_timeouts())
    except Exception as exc:
        logger.exception("human_timeout_task failed: %s", exc)
        raise self.retry(exc=exc, countdown=60) from exc
    finally:
        loop.close()


async def _async_check_timeouts() -> None:
    from app.models.lead import Lead
    from app.services.sentiment.scorer import empty_sentiment
    from sqlalchemy import text

    engine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
    )
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    reminder_delta = timedelta(minutes=settings.HUMAN_MODE_REMINDER_MINUTES)
    admin_alert_delta = timedelta(minutes=settings.HUMAN_MODE_ADMIN_ALERT_MINUTES)
    auto_release_delta = timedelta(minutes=settings.HUMAN_MODE_AUTO_RELEASE_MINUTES)

    now = datetime.now(timezone.utc)

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Lead).where(
                    Lead.human_mode.is_(True),
                    Lead.human_taken_at.isnot(None),
                )
            )
            leads: List[Lead] = list(result.scalars().all())

        if not leads:
            return

        logger.debug("human_timeout_task: checking %d human-mode leads", len(leads))

        for lead in leads:
            taken_at = lead.human_taken_at
            if taken_at.tzinfo is None:
                taken_at = taken_at.replace(tzinfo=timezone.utc)
            elapsed = now - taken_at

            try:
                if elapsed >= auto_release_delta:
                    await _auto_release(lead, db_factory=AsyncSessionLocal)
                elif elapsed >= admin_alert_delta:
                    _publish_ws_event(
                        broker_id=lead.broker_id,
                        event="human_mode_admin_alert",
                        data={
                            "lead_id": lead.id,
                            "lead_name": lead.name or lead.phone,
                            "assigned_to": lead.human_assigned_to,
                            "elapsed_minutes": int(elapsed.total_seconds() / 60),
                        },
                    )
                elif elapsed >= reminder_delta:
                    if lead.human_assigned_to:
                        _publish_ws_event(
                            broker_id=lead.broker_id,
                            event="human_mode_reminder",
                            data={
                                "lead_id": lead.id,
                                "lead_name": lead.name or lead.phone,
                                "assigned_to": lead.human_assigned_to,
                                "elapsed_minutes": int(elapsed.total_seconds() / 60),
                                "target_user_id": lead.human_assigned_to,
                            },
                        )
            except Exception as exc:
                logger.warning(
                    "human_timeout_task: error processing lead %s: %s", lead.id, exc
                )

    finally:
        await engine.dispose()


async def _auto_release(lead: Any, db_factory: Any) -> None:
    """Release a stale human_mode lead back to AI control."""
    from app.services.sentiment.scorer import empty_sentiment
    from sqlalchemy import text

    async with db_factory() as db:
        # Reset columns
        await db.execute(
            text("""
                UPDATE leads
                SET
                    human_mode = false,
                    human_assigned_to = NULL,
                    human_taken_at = NULL,
                    metadata = jsonb_set(
                        COALESCE(metadata, '{}') - 'human_mode_notified',
                        '{sentiment}',
                        CAST(:sentiment_val AS jsonb),
                        true
                    )
                WHERE id = :lid
            """),
            {
                "lid": lead.id,
                "sentiment_val": json.dumps(empty_sentiment()),
            },
        )
        await db.commit()

    logger.warning(
        "human_mode_auto_released lead_id=%s broker_id=%s elapsed_minutes=%s",
        lead.id,
        lead.broker_id,
        int((datetime.now(timezone.utc) - (
            lead.human_taken_at.replace(tzinfo=timezone.utc)
            if lead.human_taken_at.tzinfo is None
            else lead.human_taken_at
        )).total_seconds() / 60),
    )

    _publish_ws_event(
        broker_id=lead.broker_id,
        event="human_mode_auto_released",
        data={
            "lead_id": lead.id,
            "lead_name": lead.name or lead.phone,
            "previously_assigned_to": lead.human_assigned_to,
        },
    )


def _publish_ws_event(broker_id: int, event: str, data: Dict[str, Any]) -> None:
    """Publish a WebSocket event via Redis Pub/Sub.

    The API process subscribes to ws:broker:{broker_id} and delivers the
    message to all connected WebSocket clients for that broker.
    """
    import redis as sync_redis

    try:
        r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
        payload = json.dumps({
            "broker_id": broker_id,
            "event": event,
            "data": data,
            "ts": datetime.now(timezone.utc).timestamp(),
        })
        r.publish(f"ws:broker:{broker_id}", payload)
        r.close()
    except Exception as exc:
        logger.warning("human_timeout_task: failed to publish WS event: %s", exc)
