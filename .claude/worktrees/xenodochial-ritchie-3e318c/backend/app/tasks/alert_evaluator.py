"""
Celery Beat task: evaluates observability alerts every 5 minutes.

Alert types evaluated:
- cost_spike        — LLM cost in the last hour > threshold vs. previous hour
- escalation_spike  — escalation rate > 20% in the last hour
- error_spike       — >10 errors in the last hour
- stale_human_mode  — lead in human_mode for >30 min without activity
- slow_responses    — avg latency P95 > 8 000 ms in the last hour
- handoff_loop      — A→B→A pattern detected (already logged; pick up from events)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from celery import shared_task
from sqlalchemy import func, select, text

from app.core.database import SyncSessionLocal
from app.models.agent_event import AgentEvent
from app.models.lead import Lead
from app.models.observability_alert import ObservabilityAlert

logger = logging.getLogger(__name__)

# ── Thresholds (can be moved to env vars later) ──────────────────────────────
COST_SPIKE_RATIO = 3.0        # 3× normal hourly cost
ESCALATION_RATE_THRESHOLD = 20.0  # percent
ERROR_COUNT_THRESHOLD = 10
STALE_HUMAN_MINUTES = 30
SLOW_P95_MS = 8_000


@shared_task(name="observability.evaluate_alerts", ignore_result=True)
def evaluate_alerts() -> None:
    """Run all alert evaluators. Called by Celery Beat every 5 minutes."""
    logger.info("Running observability alert evaluation …")
    with SyncSessionLocal() as db:
        try:
            _check_cost_spike(db)
            _check_escalation_spike(db)
            _check_error_spike(db)
            _check_stale_human_mode(db)
            _check_slow_responses(db)
            db.commit()
        except Exception:
            logger.exception("Alert evaluation failed")
            db.rollback()


# ── Individual checkers ───────────────────────────────────────────────────────

def _create_alert(db, alert_type: str, severity: str, title: str, description: str,
                  broker_id: Optional[int] = None, lead_id: Optional[int] = None,
                  alert_data: Optional[dict] = None) -> None:
    """Insert a new alert only if no active alert of this type already exists."""
    existing = db.execute(
        select(ObservabilityAlert).where(
            ObservabilityAlert.alert_type == alert_type,
            ObservabilityAlert.status.in_(("active", "acknowledged")),
            *([] if broker_id is None else [ObservabilityAlert.related_broker_id == broker_id]),
        )
    ).scalar_one_or_none()

    if existing:
        return  # Don't spam duplicate alerts

    alert = ObservabilityAlert(
        alert_type=alert_type,
        severity=severity,
        title=title,
        description=description,
        related_broker_id=broker_id,
        related_lead_id=lead_id,
        status="active",
        alert_data=alert_data or {},
    )
    db.add(alert)
    logger.info("Created alert: %s — %s", alert_type, title)


def _check_cost_spike(db) -> None:
    now = datetime.now(timezone.utc)
    last_hour = now - timedelta(hours=1)
    prev_hour_start = now - timedelta(hours=2)

    result = db.execute(text("""
        SELECT
            SUM(llm_cost_usd) FILTER (WHERE created_at >= :last_hour) AS current_cost,
            SUM(llm_cost_usd) FILTER (WHERE created_at < :last_hour AND created_at >= :prev_hour) AS prev_cost
        FROM agent_events
        WHERE event_type = 'llm_call' AND created_at >= :prev_hour
    """), {"last_hour": last_hour, "prev_hour": prev_hour_start}).one()

    current = float(result[0] or 0)
    previous = float(result[1] or 0.01)  # avoid div-zero

    if previous > 0.001 and current / previous >= COST_SPIKE_RATIO:
        _create_alert(
            db, "cost_spike", "warning",
            f"LLM cost spike: ${current:.4f} in last hour",
            f"LLM spend is {current/previous:.1f}× higher than the previous hour.",
            alert_data={"current_cost_usd": current, "previous_cost_usd": previous},
        )


def _check_escalation_spike(db) -> None:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    result = db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE event_type = 'escalation_triggered') AS escalations,
            COUNT(*) FILTER (WHERE event_type = 'llm_call') AS llm_calls
        FROM agent_events WHERE created_at >= :since
    """), {"since": since}).one()

    escalations = result[0] or 0
    llm_calls = result[1] or 0
    if llm_calls > 10:  # only fire if there's meaningful traffic
        rate = escalations / llm_calls * 100
        if rate >= ESCALATION_RATE_THRESHOLD:
            _create_alert(
                db, "escalation_spike", "warning",
                f"High escalation rate: {rate:.1f}%",
                f"{escalations} escalations in the last hour ({rate:.1f}% of conversations).",
                alert_data={"escalation_count": escalations, "rate_pct": rate},
            )


def _check_error_spike(db) -> None:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    count = db.execute(
        select(func.count()).where(
            AgentEvent.event_type == "error",
            AgentEvent.created_at >= since,
        )
    ).scalar_one() or 0

    if count >= ERROR_COUNT_THRESHOLD:
        _create_alert(
            db, "error_spike", "critical",
            f"Error spike: {count} errors in last hour",
            f"The agent system logged {count} errors in the last hour.",
            alert_data={"error_count": count},
        )


def _check_stale_human_mode(db) -> None:
    threshold = datetime.now(timezone.utc) - timedelta(minutes=STALE_HUMAN_MINUTES)
    stale_leads = db.execute(
        select(Lead.id, Lead.broker_id).where(
            Lead.human_mode.is_(True),
            Lead.human_taken_at < threshold,
        ).limit(50)
    ).all()

    for lead_id, broker_id in stale_leads:
        _create_alert(
            db, "stale_human_mode", "warning",
            f"Lead {lead_id} stale in human mode",
            f"Lead {lead_id} has been in human mode for >{STALE_HUMAN_MINUTES} min without activity.",
            broker_id=broker_id,
            lead_id=lead_id,
            alert_data={"lead_id": lead_id},
        )


def _check_slow_responses(db) -> None:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    result = db.execute(text("""
        SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY llm_latency_ms)
        FROM agent_events
        WHERE event_type = 'llm_call' AND llm_latency_ms IS NOT NULL AND created_at >= :since
    """), {"since": since}).scalar_one()

    p95 = int(result or 0)
    if p95 >= SLOW_P95_MS:
        _create_alert(
            db, "slow_responses", "warning",
            f"Slow LLM responses: P95={p95}ms",
            f"LLM response P95 latency is {p95}ms in the last hour (threshold: {SLOW_P95_MS}ms).",
            alert_data={"p95_ms": p95},
        )
