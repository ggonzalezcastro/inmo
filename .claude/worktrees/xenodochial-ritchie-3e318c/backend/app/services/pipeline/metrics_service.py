"""
Pipeline metrics: leads by stage, stage counts, conversion metrics, inactive leads.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, func, desc, cast, Date
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, timezone, date
from typing import List, Optional, Dict, Any

from app.models.lead import Lead
from app.models.activity_log import ActivityLog
from app.services.pipeline.constants import PIPELINE_STAGES


async def get_leads_by_stage(
    db: AsyncSession,
    stage: str,
    broker_id: Optional[int] = None,
    treatment_type: Optional[str] = None,
    assigned_to: Optional[str] = None,
    search: Optional[str] = None,
    created_from: Optional[date] = None,
    created_to: Optional[date] = None,
    calificacion: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[List[Lead], int]:
    """
    Get leads in a specific pipeline stage.

    For "entrada" stage: includes leads with pipeline_stage IS NULL or pipeline_stage = "entrada"
    For other stages: includes only leads with pipeline_stage = stage
    """
    if stage not in PIPELINE_STAGES:
        raise ValueError(f"Invalid pipeline stage: {stage}")

    if stage == "entrada":
        stage_condition = or_(
            Lead.pipeline_stage.is_(None),
            Lead.pipeline_stage == "entrada",
        )
    else:
        stage_condition = Lead.pipeline_stage == stage

    query = select(Lead).options(selectinload(Lead.assigned_agent)).where(stage_condition)
    count_query = select(func.count(Lead.id)).where(stage_condition)

    if broker_id:
        query = query.where(Lead.broker_id == broker_id)
        count_query = count_query.where(Lead.broker_id == broker_id)

    if treatment_type:
        query = query.where(Lead.treatment_type == treatment_type)
        count_query = count_query.where(Lead.treatment_type == treatment_type)

    if assigned_to == "unassigned":
        query = query.where(Lead.assigned_to.is_(None))
        count_query = count_query.where(Lead.assigned_to.is_(None))
    elif assigned_to:
        try:
            agent_id_int = int(assigned_to)
            query = query.where(Lead.assigned_to == agent_id_int)
            count_query = count_query.where(Lead.assigned_to == agent_id_int)
        except (ValueError, TypeError):
            pass

    if search:
        search_pattern = f"%{search}%"
        search_cond = or_(
            Lead.name.ilike(search_pattern),
            Lead.phone.ilike(search_pattern),
        )
        query = query.where(search_cond)
        count_query = count_query.where(search_cond)

    if created_from:
        query = query.where(cast(Lead.created_at, Date) >= created_from)
        count_query = count_query.where(cast(Lead.created_at, Date) >= created_from)

    if created_to:
        query = query.where(cast(Lead.created_at, Date) <= created_to)
        count_query = count_query.where(cast(Lead.created_at, Date) <= created_to)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    if stage == "entrada":
        query = (
            query.order_by(
                desc(Lead.stage_entered_at).nulls_last(),
                desc(Lead.created_at),
            )
            .offset(skip)
            .limit(limit)
        )
    else:
        query = query.order_by(desc(Lead.stage_entered_at)).offset(skip).limit(limit)

    result = await db.execute(query)
    leads_raw = result.scalars().all()

    # Client-side filter for calificacion (JSON field) — only if requested
    if calificacion:
        leads_raw = [
            l for l in leads_raw
            if (l.lead_metadata or {}).get("calificacion") == calificacion
        ]

    return leads_raw, total


async def get_stage_metrics(
    db: AsyncSession,
    broker_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Get conversion metrics between stages, plus weekly trend and response rate."""
    stages = list(PIPELINE_STAGES.keys())
    stage_counts = {}

    for stage in stages:
        if stage == "entrada":
            query = select(func.count(Lead.id)).where(
                or_(
                    Lead.pipeline_stage.is_(None),
                    Lead.pipeline_stage == "entrada",
                )
            )
        else:
            query = select(func.count(Lead.id)).where(Lead.pipeline_stage == stage)

        if broker_id:
            query = query.where(Lead.broker_id == broker_id)

        result = await db.execute(query)
        count = result.scalar() or 0
        stage_counts[stage] = count

    total_leads = sum(stage_counts.values())
    stage_avg_days = {}

    for stage in stages:
        if stage == "entrada":
            stage_condition = or_(
                Lead.pipeline_stage.is_(None),
                Lead.pipeline_stage == "entrada",
            )
        else:
            stage_condition = Lead.pipeline_stage == stage

        query = select(Lead.stage_entered_at).where(
            and_(
                stage_condition,
                Lead.stage_entered_at.isnot(None),
            )
        )
        if broker_id:
            query = query.where(Lead.broker_id == broker_id)

        result = await db.execute(query)
        timestamps = [row[0] for row in result.all() if row[0]]

        if stage == "entrada":
            fallback_query = select(Lead.created_at).where(
                and_(
                    Lead.pipeline_stage.is_(None),
                    Lead.stage_entered_at.is_(None),
                )
            )
            if broker_id:
                fallback_query = fallback_query.where(Lead.broker_id == broker_id)
            fallback_result = await db.execute(fallback_query)
            fallback_timestamps = [row[0] for row in fallback_result.all() if row[0]]
            timestamps.extend(fallback_timestamps)

        if timestamps:
            now = datetime.now().replace(tzinfo=timestamps[0].tzinfo)
            days_list = [(now - ts).days for ts in timestamps]
            stage_avg_days[stage] = round(sum(days_list) / len(days_list), 1) if days_list else 0
        else:
            stage_avg_days[stage] = 0

    # Compute conversion rate (leads that reached "ganado" / total)
    ganado_count = stage_counts.get("ganado", 0)
    conversion_rate = round((ganado_count / total_leads * 100), 1) if total_leads else 0.0

    weekly_trend = await get_weekly_leads_trend(db, broker_id=broker_id)
    response_rate = await get_response_rate(db, broker_id=broker_id)

    return {
        "total_leads": total_leads,
        "stage_counts": stage_counts,
        "stage_avg_days": stage_avg_days,
        "stages": PIPELINE_STAGES,
        "conversion_rate": conversion_rate,
        "weekly_trend": weekly_trend,
        "response_rate": response_rate,
    }


async def get_weekly_leads_trend(
    db: AsyncSession,
    broker_id: Optional[int] = None,
    weeks: int = 8,
) -> List[Dict[str, Any]]:
    """Return the count of leads created per week for the last `weeks` weeks.

    Uses PostgreSQL date_trunc with America/Santiago timezone so week boundaries
    align with Chilean local time (UTC-3 / UTC-4 depending on DST).
    """
    # Build a raw SQL expression for date_trunc with timezone awareness
    tz_expr = func.timezone("America/Santiago", Lead.created_at)
    week_trunc = func.date_trunc("week", tz_expr)

    cutoff = datetime.now(tz=timezone.utc) - timedelta(weeks=weeks)

    query = (
        select(week_trunc.label("week_start"), func.count(Lead.id).label("count"))
        .where(Lead.created_at >= cutoff)
        .group_by(week_trunc)
        .order_by(week_trunc)
    )
    if broker_id:
        query = query.where(Lead.broker_id == broker_id)

    result = await db.execute(query)
    rows = result.all()

    trend = []
    for row in rows:
        week_start = row[0]
        count = row[1]
        if week_start:
            label = week_start.strftime("%-d %b") if hasattr(week_start, "strftime") else str(week_start)
            trend.append({"week": label, "week_start": week_start.isoformat() if hasattr(week_start, "isoformat") else str(week_start), "count": int(count)})

    return trend


async def get_response_rate(
    db: AsyncSession,
    broker_id: Optional[int] = None,
) -> float:
    """Response rate = leads that advanced past 'entrada' stage / total leads * 100.

    A lead is considered "responded to" when its pipeline_stage is anything other
    than NULL / 'entrada', meaning the AI (or agent) engaged with them and moved
    them forward in the pipeline.
    """
    total_query = select(func.count(Lead.id))
    engaged_query = select(func.count(Lead.id)).where(
        and_(
            Lead.pipeline_stage.isnot(None),
            Lead.pipeline_stage != "entrada",
        )
    )

    if broker_id:
        total_query = total_query.where(Lead.broker_id == broker_id)
        engaged_query = engaged_query.where(Lead.broker_id == broker_id)

    total_result = await db.execute(total_query)
    total = total_result.scalar() or 0

    if total == 0:
        return 0.0

    engaged_result = await db.execute(engaged_query)
    engaged = engaged_result.scalar() or 0

    return round((engaged / total) * 100, 1)


async def get_funnel_metrics(
    db: AsyncSession,
    broker_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Returns conversion funnel metrics computed from current stage counts + activity log.

    - stage_counts: current leads per stage
    - conversion_rates: % of leads that advanced from one stage to the next
    - avg_stage_days: average days leads currently spend in each stage
    - total_conversion_rate: entrada → ganado overall %
    - lost_by_stage: count of leads that were moved to 'perdido' from each stage
    """
    stages = list(PIPELINE_STAGES.keys())
    active_stages = [s for s in stages if s not in ("ganado", "perdido")]

    # Current lead counts per stage
    stage_counts: Dict[str, int] = {}
    for stage in stages:
        if stage == "entrada":
            q = select(func.count(Lead.id)).where(
                or_(Lead.pipeline_stage.is_(None), Lead.pipeline_stage == "entrada")
            )
        else:
            q = select(func.count(Lead.id)).where(Lead.pipeline_stage == stage)
        if broker_id:
            q = q.where(Lead.broker_id == broker_id)
        result = await db.execute(q)
        stage_counts[stage] = result.scalar() or 0

    total_leads = sum(stage_counts.values())

    # Conversion rates between consecutive active stages (based on current counts)
    # This is a snapshot: leads currently in later stages / leads in earlier stages
    conversion_rates: Dict[str, float] = {}
    stage_pairs = [
        ("entrada", "perfilamiento"),
        ("perfilamiento", "calificacion_financiera"),
        ("calificacion_financiera", "potencial"),
        ("calificacion_financiera", "agendado"),
        ("potencial", "agendado"),
        ("agendado", "ganado"),
    ]
    for from_s, to_s in stage_pairs:
        from_count = stage_counts.get(from_s, 0)
        to_count = stage_counts.get(to_s, 0)
        key = f"{from_s}_to_{to_s}"
        if from_count > 0:
            conversion_rates[key] = round((to_count / (from_count + to_count)) * 100, 1)
        else:
            conversion_rates[key] = 0.0

    # Avg days in current stage per stage
    avg_stage_days: Dict[str, float] = {}
    for stage in active_stages:
        if stage == "entrada":
            stage_condition = or_(Lead.pipeline_stage.is_(None), Lead.pipeline_stage == "entrada")
        else:
            stage_condition = Lead.pipeline_stage == stage

        q = select(Lead.stage_entered_at, Lead.created_at).where(stage_condition)
        if broker_id:
            q = q.where(Lead.broker_id == broker_id)
        result = await db.execute(q)
        rows = result.all()
        now = datetime.now(tz=timezone.utc)
        days_list = []
        for row in rows:
            ts = row[0] or row[1]
            if ts:
                tz = ts.tzinfo or timezone.utc
                delta = (now - ts.replace(tzinfo=tz) if ts.tzinfo is None else now - ts).days
                days_list.append(max(0, delta))
        avg_stage_days[stage] = round(sum(days_list) / len(days_list), 1) if days_list else 0.0

    # Lost by stage — query activity_logs for stage_change to "perdido"
    lost_by_stage: Dict[str, int] = {s: 0 for s in active_stages}
    try:
        q = select(ActivityLog).where(
            and_(
                ActivityLog.action_type == "stage_change",
            )
        )
        if broker_id:
            q = q.where(ActivityLog.broker_id == broker_id)
        result = await db.execute(q)
        for act in result.scalars().all():
            details = act.details or {}
            if details.get("new_stage") == "perdido":
                from_stage = details.get("old_stage", "")
                if from_stage in lost_by_stage:
                    lost_by_stage[from_stage] += 1
    except Exception:
        pass  # Non-critical

    ganado_count = stage_counts.get("ganado", 0)
    total_conversion_rate = round((ganado_count / total_leads * 100), 1) if total_leads else 0.0

    return {
        "stage_counts": stage_counts,
        "conversion_rates": conversion_rates,
        "avg_stage_days": avg_stage_days,
        "total_conversion_rate": total_conversion_rate,
        "lost_by_stage": lost_by_stage,
        "total_leads": total_leads,
    }


async def get_leads_inactive_in_stage(
    db: AsyncSession,
    stage: str,
    inactivity_days: int = 7,
    broker_id: Optional[int] = None,
) -> List[Lead]:
    """Get leads that have been in a stage for too long without activity."""
    if stage not in PIPELINE_STAGES:
        raise ValueError(f"Invalid pipeline stage: {stage}")

    cutoff_date = datetime.now() - timedelta(days=inactivity_days)
    query = select(Lead).where(
        and_(
            Lead.pipeline_stage == stage,
            Lead.stage_entered_at.isnot(None),
            Lead.stage_entered_at <= cutoff_date,
        )
    )
    if broker_id:
        query = query.where(Lead.broker_id == broker_id)
    result = await db.execute(query)
    return result.scalars().all()
