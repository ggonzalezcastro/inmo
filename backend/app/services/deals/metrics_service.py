"""
Deal metrics: stage counts, UF pipeline/closed, bank approval rate, weekly UF trend.
"""
from datetime import date, datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import Deal, DEAL_STAGES
from app.models.property import Property


async def get_deal_metrics(
    db: AsyncSession,
    broker_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Returns aggregate deal statistics for the given broker and date range.

    date_from / date_to apply to escritura_signed_at for uf_cerradas and uf_trend.
    """
    # ── Deals by stage ────────────────────────────────────────────────────────
    stage_q = select(Deal.stage, func.count(Deal.id).label("cnt")).group_by(Deal.stage)
    if broker_id:
        stage_q = stage_q.where(Deal.broker_id == broker_id)
    stage_result = await db.execute(stage_q)
    deals_by_stage: Dict[str, int] = {s: 0 for s in DEAL_STAGES}
    for row in stage_result.all():
        deals_by_stage[row[0]] = row[1]

    # ── Active deals (not cancelled) ─────────────────────────────────────────
    active_q = select(func.count(Deal.id)).where(Deal.stage != "cancelado")
    if broker_id:
        active_q = active_q.where(Deal.broker_id == broker_id)
    active_result = await db.execute(active_q)
    total_active_deals: int = active_result.scalar() or 0

    # ── UF en pipeline (active, not cancelado/escritura_firmada) ─────────────
    pipeline_q = (
        select(func.coalesce(func.sum(Property.price_uf), 0))
        .join(Deal, Deal.property_id == Property.id)
        .where(Deal.stage.notin_(["cancelado", "escritura_firmada"]))
    )
    if broker_id:
        pipeline_q = pipeline_q.where(Deal.broker_id == broker_id)
    pipeline_result = await db.execute(pipeline_q)
    uf_en_pipeline: float = float(pipeline_result.scalar() or 0)

    # ── UF cerradas (escritura_firmada, filtered by date range) ──────────────
    closed_q = (
        select(func.coalesce(func.sum(Property.price_uf), 0))
        .join(Deal, Deal.property_id == Property.id)
        .where(Deal.stage == "escritura_firmada")
    )
    if broker_id:
        closed_q = closed_q.where(Deal.broker_id == broker_id)
    if date_from:
        closed_q = closed_q.where(Deal.escritura_signed_at >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc))
    if date_to:
        closed_q = closed_q.where(Deal.escritura_signed_at < datetime(date_to.year, date_to.month, date_to.day + 1, tzinfo=timezone.utc))
    closed_result = await db.execute(closed_q)
    uf_cerradas: float = float(closed_result.scalar() or 0)

    deals_closed_q = select(func.count(Deal.id)).where(Deal.stage == "escritura_firmada")
    if broker_id:
        deals_closed_q = deals_closed_q.where(Deal.broker_id == broker_id)
    if date_from:
        deals_closed_q = deals_closed_q.where(Deal.escritura_signed_at >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc))
    if date_to:
        deals_closed_q = deals_closed_q.where(Deal.escritura_signed_at < datetime(date_to.year, date_to.month, date_to.day + 1, tzinfo=timezone.utc))
    deals_closed_result = await db.execute(deals_closed_q)
    deals_closed: int = deals_closed_result.scalar() or 0

    # ── Bank approval rate ────────────────────────────────────────────────────
    bank_total_q = select(func.count(Deal.id)).where(Deal.bank_review_status.isnot(None))
    bank_approved_q = select(func.count(Deal.id)).where(Deal.bank_review_status == "aprobado")
    if broker_id:
        bank_total_q = bank_total_q.where(Deal.broker_id == broker_id)
        bank_approved_q = bank_approved_q.where(Deal.broker_id == broker_id)
    bank_total = (await db.execute(bank_total_q)).scalar() or 0
    bank_approved = (await db.execute(bank_approved_q)).scalar() or 0
    bank_approval_rate: float = round(bank_approved / bank_total * 100, 1) if bank_total else 0.0

    # ── Weekly UF trend (escritura_firmada within date range) ─────────────────
    uf_trend = await _get_uf_trend(db, broker_id=broker_id, date_from=date_from, date_to=date_to)

    return {
        "deals_by_stage": deals_by_stage,
        "uf_en_pipeline": uf_en_pipeline,
        "uf_cerradas": uf_cerradas,
        "total_active_deals": total_active_deals,
        "deals_closed": deals_closed,
        "bank_approval_rate": bank_approval_rate,
        "uf_trend": uf_trend,
    }


async def _get_uf_trend(
    db: AsyncSession,
    broker_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """Weekly UF sum of closed deals (escritura_firmada) within the date range."""
    tz_expr = func.timezone("America/Santiago", Deal.escritura_signed_at)
    week_trunc = func.date_trunc("week", tz_expr)

    # Default: last 12 weeks if no range given
    if date_from is None:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(weeks=12)
    else:
        cutoff = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)

    q = (
        select(
            week_trunc.label("week_start"),
            func.coalesce(func.sum(Property.price_uf), 0).label("uf"),
        )
        .join(Deal, Deal.property_id == Property.id)
        .where(
            and_(
                Deal.stage == "escritura_firmada",
                Deal.escritura_signed_at.isnot(None),
                Deal.escritura_signed_at >= cutoff,
            )
        )
        .group_by(week_trunc)
        .order_by(week_trunc)
    )

    if broker_id:
        q = q.where(Deal.broker_id == broker_id)

    if date_to:
        end = datetime(date_to.year, date_to.month, date_to.day + 1, tzinfo=timezone.utc)
        q = q.where(Deal.escritura_signed_at < end)

    result = await db.execute(q)
    trend = []
    for row in result.all():
        week_start = row[0]
        uf = float(row[1])
        if week_start:
            label = week_start.strftime("%-d %b") if hasattr(week_start, "strftime") else str(week_start)
            trend.append({
                "week": label,
                "week_start": week_start.isoformat() if hasattr(week_start, "isoformat") else str(week_start),
                "uf": uf,
            })
    return trend
