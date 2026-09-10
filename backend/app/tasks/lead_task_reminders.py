"""Celery Beat job that retries in-app reminders until the client acknowledges them."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.database import SyncSessionLocal
from app.models.lead_follow_up import LeadTask, TASK_ACTIVE_STATUSES
from app.tasks.base import DLQTask


logger = logging.getLogger(__name__)

_RETRY_AFTER = timedelta(minutes=5)


@shared_task(
    name="app.tasks.lead_task_reminders.send_due_lead_task_reminders",
    base=DLQTask,
    bind=True,
    max_retries=2,
    ignore_result=True,
)
def send_due_lead_task_reminders(self) -> None:
    """Claim eligible reminders transactionally, then notify each assignee."""
    try:
        reminders = _claim_due_reminders()
    except Exception as exc:
        logger.exception("lead task reminder query failed")
        raise self.retry(exc=exc, countdown=30) from exc

    for reminder in reminders:
        if not _publish_reminder(reminder):
            # Redis was unavailable (or had no WebSocket listeners). Release the
            # claim so the next minutely run can try again immediately.
            _release_reminder_claim(reminder["task_id"], reminder["_claimed_at"])


def _claim_due_reminders(limit: int = 200) -> list[dict]:
    """Claim due, unacknowledged reminders while preventing parallel duplicates."""
    now = datetime.now(timezone.utc)
    retry_before = now - _RETRY_AFTER
    with SyncSessionLocal() as db:
        tasks = list(db.execute(
            select(LeadTask)
            .options(joinedload(LeadTask.lead))
            .where(
                LeadTask.status.in_(TASK_ACTIVE_STATUSES),
                LeadTask.assigned_to.is_not(None),
                LeadTask.reminder_at.is_not(None),
                LeadTask.reminder_at <= now,
                LeadTask.reminder_acknowledged_at.is_(None),
                or_(
                    LeadTask.reminder_sent_at.is_(None),
                    LeadTask.reminder_sent_at <= retry_before,
                ),
            )
            .order_by(LeadTask.reminder_at.asc(), LeadTask.id.asc())
            .with_for_update(of=LeadTask, skip_locked=True)
            .limit(limit)
        ).unique().scalars().all())

        payloads = []
        for task in tasks:
            task.reminder_sent_at = now
            payloads.append({
                "task_id": task.id,
                "lead_id": task.lead_id,
                "lead_name": task.lead.name if task.lead else None,
                "title": task.title,
                "due_at": task.due_at.isoformat(),
                "assigned_to": task.assigned_to,
                "broker_id": task.broker_id,
                "_claimed_at": now,
            })
        db.commit()
        return payloads


def _publish_reminder(reminder: dict) -> bool:
    """Publish to the assignee channel; return whether Redis accepted it."""
    import redis as sync_redis

    broker_id = reminder["broker_id"]
    user_id = reminder["assigned_to"]
    client = None
    try:
        client = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
        public_data = {
            key: value
            for key, value in reminder.items()
            if key not in {"broker_id", "_claimed_at"}
        }
        payload = json.dumps({
            "broker_id": broker_id,
            "event": "lead_task_reminder",
            "data": public_data,
            "ts": datetime.now(timezone.utc).timestamp(),
        })
        subscribers = client.publish(f"ws:user:{broker_id}:{user_id}", payload)
        return subscribers > 0
    except Exception as exc:
        logger.warning(
            "lead task reminder publish failed task_id=%s user_id=%s: %s",
            reminder.get("task_id"),
            user_id,
            exc,
        )
        return False
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def _release_reminder_claim(task_id: int, claimed_at: datetime) -> None:
    """Release only the failed delivery attempt represented by ``claimed_at``."""
    try:
        with SyncSessionLocal() as db:
            task = db.scalar(
                select(LeadTask).where(
                    LeadTask.id == task_id,
                    LeadTask.reminder_sent_at == claimed_at,
                    LeadTask.reminder_acknowledged_at.is_(None),
                )
            )
            if task is not None:
                task.reminder_sent_at = None
                db.commit()
    except Exception:
        # A failed release is safe: the normal five-minute retry window still
        # makes the reminder eligible again.
        logger.exception("lead task reminder claim release failed task_id=%s", task_id)
