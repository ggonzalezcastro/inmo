"""
Deal side-effects — applied after a state machine transition.

Called by the router after transition() updates deal.stage.
Handles:
  - Property.status changes (available → reserved → sold)
  - Lead.pipeline_stage changes
  - ActivityLog entries
  - WebSocket broadcast to broker
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websocket_manager import ws_manager
from app.models.activity_log import ActivityLog
from app.models.deal import Deal
from app.models.lead import Lead
from app.models.property import Property
from app.services.deals.metrics import record_stage_transition, record_time_in_stage

# Maps each stage to the Deal attribute that records when the deal *entered* that stage.
_STAGE_ENTRY_ATTR: dict[str, str] = {
    "reserva": "reserva_at",
    "docs_pendientes": None,        # no dedicated timestamp
    "en_aprobacion_bancaria": "bank_decision_at",
    "promesa_redaccion": None,
    "promesa_firmada": "promesa_signed_at",
    "escritura_firmada": "escritura_signed_at",
    "cancelado": "cancelled_at",
}


async def apply_transition_effects(
    deal: Deal,
    from_stage: str,
    to_stage: str,
    db: AsyncSession,
    actor_user_id: int | None = None,
) -> None:
    """
    Apply side-effects of a deal stage transition.
    Idempotent: safe to call multiple times (checks current state before acting).
    """
    now = datetime.now(timezone.utc)

    await _update_property_status(deal, to_stage, db)
    await _update_lead_pipeline(deal, to_stage, db, now)
    await _log_activity(deal, from_stage, to_stage, actor_user_id, db, now)
    await _broadcast(deal, from_stage, to_stage)

    record_stage_transition(from_stage=from_stage, to_stage=to_stage)
    _record_time_in_from_stage(deal, from_stage, now)


# ── Metrics helpers ───────────────────────────────────────────────────────────

def _record_time_in_from_stage(deal: Deal, from_stage: str, now: datetime) -> None:
    """Observe how long the deal spent in from_stage using stored stage timestamps."""
    attr = _STAGE_ENTRY_ATTR.get(from_stage)
    entry_ts = getattr(deal, attr, None) if attr else None
    if entry_ts is None:
        # Fall back to deal.created_at for the very first stage (draft)
        if from_stage == "draft" and deal.created_at is not None:
            entry_ts = deal.created_at
    if entry_ts is not None:
        elapsed = (now - entry_ts).total_seconds()
        if elapsed >= 0:
            record_time_in_stage(stage=from_stage, seconds=elapsed)


# ── Property status ───────────────────────────────────────────────────────────

async def _update_property_status(deal: Deal, to_stage: str, db: AsyncSession) -> None:
    if to_stage not in ("reserva", "escritura_firmada", "cancelado"):
        return

    result = await db.execute(select(Property).where(Property.id == deal.property_id))
    prop = result.scalar_one_or_none()
    if prop is None:
        return

    if to_stage == "reserva" and prop.status != "reserved":
        prop.status = "reserved"
        db.add(prop)
        await ws_manager.broadcast(
            broker_id=deal.broker_id,
            event="property_status_changed",
            data={"property_id": deal.property_id, "status": "reserved", "deal_id": deal.id},
        )
    elif to_stage == "escritura_firmada" and prop.status != "sold":
        prop.status = "sold"
        db.add(prop)
        await ws_manager.broadcast(
            broker_id=deal.broker_id,
            event="property_status_changed",
            data={"property_id": deal.property_id, "status": "sold", "deal_id": deal.id},
        )
    elif to_stage == "cancelado" and prop.status != "available":
        prop.status = "available"
        db.add(prop)
        await ws_manager.broadcast(
            broker_id=deal.broker_id,
            event="property_status_changed",
            data={"property_id": deal.property_id, "status": "available", "deal_id": deal.id},
        )


# ── Lead pipeline stage ───────────────────────────────────────────────────────

async def _update_lead_pipeline(
    deal: Deal,
    to_stage: str,
    db: AsyncSession,
    now: datetime,
) -> None:
    if to_stage not in ("reserva", "escritura_firmada", "cancelado"):
        return

    result = await db.execute(select(Lead).where(Lead.id == deal.lead_id))
    lead = result.scalar_one_or_none()
    if lead is None:
        return

    if to_stage == "reserva":
        if lead.pipeline_stage != "agendado":
            lead.pipeline_stage = "agendado"
            db.add(lead)

    elif to_stage == "escritura_firmada":
        if lead.pipeline_stage != "ganado":
            lead.pipeline_stage = "ganado"
            lead.closed_at = now
            lead.close_reason = "deal_ganado"
            db.add(lead)

    elif to_stage == "cancelado":
        if lead.pipeline_stage != "perdido":
            lead.pipeline_stage = "perdido"
            lead.closed_at = now
            lead.close_reason = "deal_cancelado"
            lead.close_reason_detail = deal.cancellation_notes
            db.add(lead)


# ── ActivityLog ───────────────────────────────────────────────────────────────

async def _log_activity(
    deal: Deal,
    from_stage: str,
    to_stage: str,
    actor_user_id: int | None,
    db: AsyncSession,
    now: datetime,
) -> None:
    activity = ActivityLog(
        lead_id=deal.lead_id,
        action_type="deal_stage_changed",
        details={
            "deal_id": deal.id,
            "property_id": deal.property_id,
            "from_stage": from_stage,
            "to_stage": to_stage,
            "actor_user_id": actor_user_id,
        },
        timestamp=now,
    )
    db.add(activity)


# ── WebSocket broadcast ───────────────────────────────────────────────────────

async def _broadcast(deal: Deal, from_stage: str, to_stage: str) -> None:
    await ws_manager.broadcast(
        broker_id=deal.broker_id,
        event="deal_stage_changed",
        data={
            "deal_id": deal.id,
            "lead_id": deal.lead_id,
            "property_id": deal.property_id,
            "from_stage": from_stage,
            "to_stage": to_stage,
        },
    )
