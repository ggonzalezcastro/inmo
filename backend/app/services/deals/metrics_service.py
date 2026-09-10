"""Sales metrics for deals, scoped by broker and optionally by assigned agent."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.deal import DEAL_STAGES, Deal
from app.models.lead import Lead
from app.models.project import Project
from app.models.property import Property


SANTIAGO_TZ = ZoneInfo("America/Santiago")
MONTH_NAMES_ES = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sept",
    "oct",
    "nov",
    "dic",
)


def _price_uf():
    """Best available selling price in UF, without converting from CLP."""
    return func.coalesce(
        case(
            (Property.has_offer.is_(True), Property.offer_price_uf),
            else_=None,
        ),
        Property.list_price_uf,
        Property.price_uf,
        0,
    )


def _price_clp():
    """Best available selling price in CLP, without converting from UF."""
    return func.coalesce(
        case(
            (Property.has_offer.is_(True), Property.offer_price_clp),
            else_=None,
        ),
        Property.list_price_clp,
        Property.price_clp,
        0,
    )


def _date_bounds(
    date_from: Optional[date],
    date_to: Optional[date],
) -> Tuple[Optional[datetime], Optional[datetime]]:
    start = (
        datetime.combine(date_from, time.min, tzinfo=SANTIAGO_TZ).astimezone(
            timezone.utc
        )
        if date_from
        else None
    )
    end = (
        datetime.combine(
            date_to + timedelta(days=1), time.min, tzinfo=SANTIAGO_TZ
        ).astimezone(timezone.utc)
        if date_to
        else None
    )
    return start, end


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _shift_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, 1)


def _delta_percent(current: float, previous: float) -> Optional[float]:
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _period_label(period: datetime, granularity: str) -> str:
    month = MONTH_NAMES_ES[period.month - 1]
    return f"{period.day} {month}" if granularity == "week" else f"{month} {period.year}"


def _scope(
    query: Select,
    broker_id: Optional[int],
    agent_id: Optional[int],
) -> Select:
    if broker_id is not None:
        query = query.where(Deal.broker_id == broker_id)
    if agent_id is not None:
        lead_ids = select(Lead.id).where(Lead.assigned_to == agent_id)
        if broker_id is not None:
            lead_ids = lead_ids.where(Lead.broker_id == broker_id)
        query = query.where(Deal.lead_id.in_(lead_ids))
    return query


def _apply_event_period(
    query: Select,
    event_column: Any,
    date_from: Optional[date],
    date_to: Optional[date],
) -> Select:
    start, end = _date_bounds(date_from, date_to)
    if start is not None:
        query = query.where(event_column >= start)
    if end is not None:
        query = query.where(event_column < end)
    return query


async def _sales_summary(
    db: AsyncSession,
    broker_id: Optional[int],
    agent_id: Optional[int],
    start: date,
    end: date,
) -> Dict[str, Any]:
    start_dt, end_dt = _date_bounds(start, end)
    query = (
        select(
            func.count(Deal.id),
            func.coalesce(func.sum(_price_uf()), 0),
            func.coalesce(func.sum(_price_clp()), 0),
        )
        .select_from(Deal)
        .join(Property, Deal.property_id == Property.id)
        .where(
            Deal.stage == "escritura_firmada",
            Deal.escritura_signed_at.isnot(None),
            Deal.escritura_signed_at >= start_dt,
            Deal.escritura_signed_at < end_dt,
        )
    )
    result = (await db.execute(_scope(query, broker_id, agent_id))).one()
    return {
        "sales": int(result[0] or 0),
        "uf": float(result[1] or 0),
        "clp": int(result[2] or 0),
    }


async def _comparison_summary(
    db: AsyncSession,
    broker_id: Optional[int],
    agent_id: Optional[int],
    start: date,
    end: date,
    previous_start: date,
    previous_end: date,
) -> Dict[str, Any]:
    current = await _sales_summary(db, broker_id, agent_id, start, end)
    previous = await _sales_summary(
        db, broker_id, agent_id, previous_start, previous_end
    )
    return {
        **current,
        "previous_sales": previous["sales"],
        "previous_uf": previous["uf"],
        "sales_delta_percent": _delta_percent(current["sales"], previous["sales"]),
        "uf_delta_percent": _delta_percent(current["uf"], previous["uf"]),
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
    }


async def _event_count(
    db: AsyncSession,
    event_column: Any,
    broker_id: Optional[int],
    agent_id: Optional[int],
    date_from: Optional[date],
    date_to: Optional[date],
) -> int:
    query = select(func.count(Deal.id)).where(event_column.isnot(None))
    query = _apply_event_period(query, event_column, date_from, date_to)
    return int((await db.execute(_scope(query, broker_id, agent_id))).scalar() or 0)


async def _sales_trend(
    db: AsyncSession,
    granularity: str,
    broker_id: Optional[int],
    agent_id: Optional[int],
    date_from: Optional[date],
    date_to: Optional[date],
) -> List[Dict[str, Any]]:
    anchor = date_to or datetime.now(tz=timezone.utc).date()
    if date_from is not None:
        cutoff_date = date_from
    elif granularity == "week":
        cutoff_date = anchor - timedelta(weeks=12)
    else:
        cutoff_date = _shift_months(_month_start(anchor), -11)

    cutoff, end = _date_bounds(cutoff_date, anchor)
    local_timestamp = func.timezone("America/Santiago", Deal.escritura_signed_at)
    period_start = func.date_trunc(granularity, local_timestamp)

    query = (
        select(
            period_start.label("period_start"),
            func.count(Deal.id).label("sales"),
            func.coalesce(func.sum(_price_uf()), 0).label("uf"),
            func.coalesce(func.sum(_price_clp()), 0).label("clp"),
        )
        .select_from(Deal)
        .join(Property, Deal.property_id == Property.id)
        .where(
            Deal.stage == "escritura_firmada",
            Deal.escritura_signed_at.isnot(None),
            Deal.escritura_signed_at >= cutoff,
            Deal.escritura_signed_at < end,
        )
        .group_by(period_start)
        .order_by(period_start)
    )
    rows = (await db.execute(_scope(query, broker_id, agent_id))).all()

    points: List[Dict[str, Any]] = []
    for period, sales, uf, clp in rows:
        if not period:
            continue
        if granularity == "week":
            points.append(
                {
                    "week": _period_label(period, granularity),
                    "week_start": period.isoformat(),
                    "sales": int(sales or 0),
                    "uf": float(uf or 0),
                    "clp": int(clp or 0),
                }
            )
        else:
            points.append(
                {
                    "month": _period_label(period, granularity),
                    "month_start": period.isoformat(),
                    "sales": int(sales or 0),
                    "uf": float(uf or 0),
                    "clp": int(clp or 0),
                }
            )
    return points


async def get_deal_metrics(
    db: AsyncSession,
    broker_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    agent_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Return operational sales metrics for a broker or a single agent."""

    stage_query = select(Deal.stage, func.count(Deal.id)).group_by(Deal.stage)
    stage_rows = (await db.execute(_scope(stage_query, broker_id, agent_id))).all()
    deals_by_stage: Dict[str, int] = {stage: 0 for stage in DEAL_STAGES}
    for stage, count in stage_rows:
        deals_by_stage[stage] = int(count or 0)

    active_query = select(func.count(Deal.id)).where(
        Deal.stage.notin_(["cancelado", "escritura_firmada"])
    )
    total_active_deals = int(
        (await db.execute(_scope(active_query, broker_id, agent_id))).scalar() or 0
    )

    pipeline_query = (
        select(func.coalesce(func.sum(_price_uf()), 0))
        .select_from(Deal)
        .join(Property, Deal.property_id == Property.id)
        .where(Deal.stage.notin_(["cancelado", "escritura_firmada"]))
    )
    uf_en_pipeline = float(
        (await db.execute(_scope(pipeline_query, broker_id, agent_id))).scalar() or 0
    )

    closed_query = (
        select(
            func.count(Deal.id),
            func.coalesce(func.sum(_price_uf()), 0),
            func.coalesce(func.sum(_price_clp()), 0),
        )
        .select_from(Deal)
        .join(Property, Deal.property_id == Property.id)
        .where(Deal.stage == "escritura_firmada")
    )
    closed_query = _apply_event_period(
        closed_query, Deal.escritura_signed_at, date_from, date_to
    )
    closed = (await db.execute(_scope(closed_query, broker_id, agent_id))).one()
    deals_closed = int(closed[0] or 0)
    uf_cerradas = float(closed[1] or 0)
    clp_cerradas = int(closed[2] or 0)

    bank_total_query = select(func.count(Deal.id)).where(
        Deal.bank_review_status.in_(["aprobado", "rechazado"]),
        Deal.bank_decision_at.isnot(None),
    )
    bank_approved_query = select(func.count(Deal.id)).where(
        Deal.bank_review_status == "aprobado",
        Deal.bank_decision_at.isnot(None),
    )
    bank_total_query = _apply_event_period(
        bank_total_query, Deal.bank_decision_at, date_from, date_to
    )
    bank_approved_query = _apply_event_period(
        bank_approved_query, Deal.bank_decision_at, date_from, date_to
    )
    bank_total = int(
        (await db.execute(_scope(bank_total_query, broker_id, agent_id))).scalar() or 0
    )
    bank_approved = int(
        (await db.execute(_scope(bank_approved_query, broker_id, agent_id))).scalar()
        or 0
    )
    bank_approval_rate = round(bank_approved / bank_total * 100, 1) if bank_total else 0.0

    reservations_period = await _event_count(
        db, Deal.reserva_at, broker_id, agent_id, date_from, date_to
    )
    promises_signed_period = await _event_count(
        db, Deal.promesa_signed_at, broker_id, agent_id, date_from, date_to
    )
    cancellations_period = await _event_count(
        db, Deal.cancelled_at, broker_id, agent_id, date_from, date_to
    )
    cancellation_base = deals_closed + cancellations_period
    cancellation_rate = (
        round(cancellations_period / cancellation_base * 100, 1)
        if cancellation_base
        else 0.0
    )

    cycle_query = select(
        func.avg(
            func.extract("epoch", Deal.escritura_signed_at - Deal.created_at) / 86400.0
        ),
        func.avg(
            func.extract("epoch", Deal.escritura_signed_at - Deal.reserva_at) / 86400.0
        ),
    ).where(
        Deal.stage == "escritura_firmada",
        Deal.escritura_signed_at.isnot(None),
    )
    cycle_query = _apply_event_period(
        cycle_query, Deal.escritura_signed_at, date_from, date_to
    )
    cycle = (await db.execute(_scope(cycle_query, broker_id, agent_id))).one()
    avg_sales_cycle_days = round(float(cycle[0]), 1) if cycle[0] is not None else None
    avg_reservation_to_close_days = (
        round(float(cycle[1]), 1) if cycle[1] is not None else None
    )

    anchor = date_to or datetime.now(tz=timezone.utc).date()
    current_week_start = anchor - timedelta(days=anchor.weekday())
    current_week_end = anchor
    previous_week_start = current_week_start - timedelta(days=7)
    previous_week_end = previous_week_start + (anchor - current_week_start)
    sales_this_week = await _comparison_summary(
        db,
        broker_id,
        agent_id,
        current_week_start,
        current_week_end,
        previous_week_start,
        previous_week_end,
    )

    current_month_start = _month_start(anchor)
    previous_month_start = _shift_months(current_month_start, -1)
    previous_month_last_day = current_month_start - timedelta(days=1)
    previous_month_end = min(
        previous_month_start + timedelta(days=anchor.day - 1),
        previous_month_last_day,
    )
    sales_this_month = await _comparison_summary(
        db,
        broker_id,
        agent_id,
        current_month_start,
        anchor,
        previous_month_start,
        previous_month_end,
    )

    weekly_trend = await _sales_trend(
        db, "week", broker_id, agent_id, date_from, date_to
    )
    monthly_trend = await _sales_trend(
        db, "month", broker_id, agent_id, date_from, date_to
    )

    project_name = func.coalesce(Project.name, "Sin proyecto")
    projects_query = (
        select(
            Property.project_id,
            project_name.label("project_name"),
            func.count(Deal.id).label("sales"),
            func.coalesce(func.sum(_price_uf()), 0).label("uf"),
            func.coalesce(func.sum(_price_clp()), 0).label("clp"),
        )
        .select_from(Deal)
        .join(Property, Deal.property_id == Property.id)
        .outerjoin(Project, Property.project_id == Project.id)
        .where(Deal.stage == "escritura_firmada")
        .group_by(Property.project_id, Project.name)
        .order_by(func.count(Deal.id).desc(), func.sum(_price_uf()).desc())
        .limit(8)
    )
    projects_query = _apply_event_period(
        projects_query, Deal.escritura_signed_at, date_from, date_to
    )
    project_rows = (await db.execute(_scope(projects_query, broker_id, agent_id))).all()
    sales_by_project = [
        {
            "project_id": project_id,
            "project_name": name,
            "sales": int(sales or 0),
            "uf": float(uf or 0),
            "clp": int(clp or 0),
        }
        for project_id, name, sales, uf, clp in project_rows
    ]

    return {
        "deals_by_stage": deals_by_stage,
        "uf_en_pipeline": uf_en_pipeline,
        "uf_cerradas": uf_cerradas,
        "clp_cerradas": clp_cerradas,
        "total_active_deals": total_active_deals,
        "deals_closed": deals_closed,
        "bank_approval_rate": bank_approval_rate,
        "avg_ticket_uf": round(uf_cerradas / deals_closed, 1) if deals_closed else 0.0,
        "avg_ticket_clp": round(clp_cerradas / deals_closed) if deals_closed else 0,
        "reservations_period": reservations_period,
        "promises_signed_period": promises_signed_period,
        "cancellations_period": cancellations_period,
        "cancellation_rate": cancellation_rate,
        "avg_sales_cycle_days": avg_sales_cycle_days,
        "avg_reservation_to_close_days": avg_reservation_to_close_days,
        "sales_this_week": sales_this_week,
        "sales_this_month": sales_this_month,
        "uf_trend": weekly_trend,
        "monthly_trend": monthly_trend,
        "sales_by_project": sales_by_project,
    }
