"""
Pipeline metrics: leads by stage, stage counts, conversion metrics, inactive leads.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from app.models.lead import Lead
from app.services.pipeline.constants import PIPELINE_STAGES


async def get_leads_by_stage(
    db: AsyncSession,
    stage: str,
    broker_id: Optional[int] = None,
    treatment_type: Optional[str] = None,
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

    query = select(Lead).where(stage_condition)
    count_query = select(func.count(Lead.id)).where(stage_condition)

    if broker_id:
        query = query.where(Lead.assigned_to == broker_id)
        count_query = count_query.where(Lead.assigned_to == broker_id)

    if treatment_type:
        query = query.where(Lead.treatment_type == treatment_type)
        count_query = count_query.where(Lead.treatment_type == treatment_type)

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
    leads = result.scalars().all()
    return leads, total


async def get_stage_metrics(
    db: AsyncSession,
    broker_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Get conversion metrics between stages."""
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
            query = query.where(Lead.assigned_to == broker_id)

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
            query = query.where(Lead.assigned_to == broker_id)

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
                fallback_query = fallback_query.where(Lead.assigned_to == broker_id)
            fallback_result = await db.execute(fallback_query)
            fallback_timestamps = [row[0] for row in fallback_result.all() if row[0]]
            timestamps.extend(fallback_timestamps)

        if timestamps:
            now = datetime.now().replace(tzinfo=timestamps[0].tzinfo)
            days_list = [(now - ts).days for ts in timestamps]
            stage_avg_days[stage] = sum(days_list) / len(days_list) if days_list else 0
        else:
            stage_avg_days[stage] = 0

    return {
        "total_leads": total_leads,
        "stage_counts": stage_counts,
        "stage_avg_days": stage_avg_days,
        "stages": PIPELINE_STAGES,
    }


async def get_leads_inactive_in_stage(
    db: AsyncSession,
    stage: str,
    inactivity_days: int = 7,
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
    result = await db.execute(query)
    return result.scalars().all()
