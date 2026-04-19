"""
Dead Letter Queue periodic alert task (TASK-029).

Runs every 15 minutes (via Celery Beat). Emits a WARNING log when the DLQ
contains entries so that log-based alerting (Datadog, CloudWatch, etc.) can
trigger notifications. Extend alert_channel() to send Slack/email if desired.
"""
from __future__ import annotations

import asyncio
import logging

from celery import shared_task

logger = logging.getLogger(__name__)

# Alert when DLQ has at least this many entries
_ALERT_THRESHOLD = 1


@shared_task(name="app.tasks.dlq_tasks.dlq_alert_check")
def dlq_alert_check() -> None:
    """Check DLQ size and emit alert log when above threshold."""
    asyncio.run(_async_check())


async def _async_check() -> None:
    from app.tasks.dlq import DLQManager

    count = await DLQManager.count()
    if count >= _ALERT_THRESHOLD:
        logger.warning(
            "[DLQ] ALERT: %d failed task(s) in DLQ — visit "
            "GET /api/v1/admin/tasks/failed to review.",
            count,
        )
        # ── Extension point ───────────────────────────────────────────────
        # Uncomment and configure to send Slack/email notifications:
        # await _send_slack_alert(count)
        # await _send_email_alert(count)
    else:
        logger.debug("[DLQ] Check: 0 failed tasks in DLQ.")
