"""Response-time metrics for leads.

Measures how quickly a lead replies to bot/agent messages and decides
whether to apply the ``respuesta_rapida`` tag.

The function ``compute_response_metrics`` is pure (no DB access) and operates
on any iterable of objects exposing ``direction`` and ``created_at`` — the
existing ``TelegramMessage`` / ``ChatMessage`` rows both qualify.
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any, Dict, Iterable, List, Optional

from app.services.leads.constants import (
    FAST_RESPONDER_TAG,
    FAST_RESPONSE_MIN_REPLIES,
    FAST_RESPONSE_THRESHOLD_SECONDS,
)


# Empty / "no signal" payload used when the lead does not yet have any
# bot→lead reply pair.
_EMPTY_METRICS: Dict[str, Any] = {
    "reply_count": 0,
    "avg_response_seconds": None,
    "median_response_seconds": None,
    "fast_reply_count": 0,
    "last_response_seconds": None,
    "is_fast_responder": False,
    "threshold_seconds": FAST_RESPONSE_THRESHOLD_SECONDS,
    "min_replies_required": FAST_RESPONSE_MIN_REPLIES,
}


def _direction_str(value: Any) -> str:
    """Coerce a direction enum / string to its raw value (``"in"`` / ``"out"``)."""
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return str(raw).lower()


def compute_response_metrics(messages: Iterable[Any]) -> Dict[str, Any]:
    """Compute response-time metrics from a sequence of messages.

    Each message must expose ``direction`` (``"in"``/``"out"`` or
    :class:`MessageDirection`) and ``created_at`` (timezone-aware
    :class:`datetime`).

    For every consecutive ``OUTBOUND → INBOUND`` pair we record
    ``inbound.created_at - outbound.created_at`` as one reply turnaround.
    Multiple inbound messages in a row only count once (against the most
    recent outbound). Inbound messages that occur before any outbound (e.g.
    the very first user message) are ignored — there is nothing to time.
    """
    sorted_msgs: List[Any] = sorted(
        (m for m in messages if getattr(m, "created_at", None) is not None),
        key=lambda m: m.created_at,
    )

    deltas: List[float] = []
    pending_outbound_at: Optional[datetime] = None
    last_outbound_at: Optional[datetime] = None

    for msg in sorted_msgs:
        direction = _direction_str(getattr(msg, "direction", None))
        ts: datetime = msg.created_at
        if direction == "out":
            pending_outbound_at = ts
            last_outbound_at = ts
        elif direction == "in":
            if pending_outbound_at is not None:
                delta = (ts - pending_outbound_at).total_seconds()
                # Defensive: ignore non-positive or absurd values that could
                # arise from clock skew.
                if delta > 0:
                    deltas.append(delta)
                pending_outbound_at = None  # consumed by this reply

    if not deltas:
        payload = dict(_EMPTY_METRICS)
        payload["last_computed_at"] = datetime.now(timezone.utc).isoformat()
        return payload

    avg = sum(deltas) / len(deltas)
    med = median(deltas)
    fast_count = sum(1 for d in deltas if d <= FAST_RESPONSE_THRESHOLD_SECONDS)
    is_fast = (
        len(deltas) >= FAST_RESPONSE_MIN_REPLIES
        and avg <= FAST_RESPONSE_THRESHOLD_SECONDS
    )

    return {
        "reply_count": len(deltas),
        "avg_response_seconds": round(avg, 2),
        "median_response_seconds": round(med, 2),
        "fast_reply_count": fast_count,
        "last_response_seconds": round(deltas[-1], 2),
        "is_fast_responder": is_fast,
        "threshold_seconds": FAST_RESPONSE_THRESHOLD_SECONDS,
        "min_replies_required": FAST_RESPONSE_MIN_REPLIES,
        "last_computed_at": datetime.now(timezone.utc).isoformat(),
    }


def apply_fast_responder_tag(tags: Optional[List[str]], metrics: Dict[str, Any]) -> tuple[List[str], bool]:
    """Add or remove the fast-responder tag based on ``metrics``.

    Returns ``(new_tags, changed)``. ``new_tags`` is always a fresh list — the
    caller can safely assign it to ``Lead.tags``. ``changed`` indicates
    whether the tag set actually changed.
    """
    current = list(tags or [])
    has_tag = FAST_RESPONDER_TAG in current
    should_have = bool(metrics.get("is_fast_responder"))

    if should_have and not has_tag:
        current.append(FAST_RESPONDER_TAG)
        return current, True
    if not should_have and has_tag:
        current = [t for t in current if t != FAST_RESPONDER_TAG]
        return current, True
    return current, False


async def update_lead_response_metrics(db, lead_id: int) -> Dict[str, Any]:
    """Recompute response metrics for ``lead_id``, persist them to
    ``lead_metadata.response_metrics`` atomically, and apply/remove the
    fast-responder tag if needed.

    Returns a dict::

        {"metrics": <metrics>, "tag_changed": bool, "applied": bool, "new_tags": [...]}

    The PostgreSQL path uses ``jsonb_set`` so concurrent writes to other
    metadata keys (e.g. sentiment) are not clobbered. The SQLite path
    (used by the test suite) falls back to a full-dict ORM assignment.

    The caller is responsible for committing the transaction.
    """
    import json as _json
    from sqlalchemy import text as _sa_text
    from sqlalchemy.future import select as _sa_select

    from app.models.lead import Lead
    from app.models.telegram_message import TelegramMessage

    msg_result = await db.execute(
        _sa_select(TelegramMessage)
        .where(TelegramMessage.lead_id == lead_id)
        .order_by(TelegramMessage.created_at.asc())
    )
    messages = msg_result.scalars().all()
    metrics = compute_response_metrics(messages)

    lead_result = await db.execute(_sa_select(Lead).where(Lead.id == lead_id))
    lead = lead_result.scalars().first()
    if lead is None:
        return {"metrics": metrics, "tag_changed": False, "applied": False, "new_tags": []}

    new_tags, tag_changed = apply_fast_responder_tag(lead.tags, metrics)

    dialect = db.bind.dialect.name if db.bind is not None else (
        db.get_bind().dialect.name
    )
    if dialect == "postgresql":
        await db.execute(
            _sa_text(
                "UPDATE leads SET metadata = "
                "jsonb_set(COALESCE(metadata, '{}'::jsonb), "
                "ARRAY['response_metrics'], CAST(:m AS jsonb), true) "
                "WHERE id = :lid"
            ),
            {"m": _json.dumps(metrics), "lid": lead_id},
        )
    else:
        merged = dict(lead.lead_metadata or {})
        merged["response_metrics"] = metrics
        lead.lead_metadata = merged

    if tag_changed:
        lead.tags = new_tags

    return {
        "metrics": metrics,
        "tag_changed": tag_changed,
        "applied": FAST_RESPONDER_TAG in new_tags,
        "new_tags": new_tags,
    }
