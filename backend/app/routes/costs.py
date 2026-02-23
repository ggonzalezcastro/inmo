"""
LLM cost dashboard endpoints.

Provides cost visibility per broker over configurable time periods.
Data comes from the llm_calls table (TASK-006).

Endpoints:
    GET  /api/v1/admin/costs/summary      — aggregated cost summary
    GET  /api/v1/admin/costs/daily        — day-by-day breakdown (for charts)
    GET  /api/v1/admin/costs/outliers     — most expensive conversations
    GET  /api/v1/admin/costs/export       — CSV export of detailed rows
    GET  /api/v1/admin/costs/by-broker    — cost per broker (SUPERADMIN only)
    GET  /api/v1/admin/costs/calls       — paginated list of LLM calls
"""
from __future__ import annotations

import csv
import io
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.llm_call import LLMCall
from app.models.broker import Broker

router = APIRouter()


# ── Alert threshold (env-configurable) ───────────────────────────────────────

def _alert_threshold() -> float:
    try:
        return float(os.getenv("DAILY_COST_ALERT_USD", "10.0"))
    except ValueError:
        return 10.0


# ── Auth helper ───────────────────────────────────────────────────────────────

def _check_admin(current_user: dict, target_broker_id: Optional[int]) -> int:
    """
    Validate access and return the effective broker_id.
    SUPERADMIN can query any broker (must pass broker_id).
    ADMIN can only query their own broker.
    """
    role = (current_user.get("role") or "").upper()
    user_broker_id = current_user.get("broker_id")

    if role == "SUPERADMIN":
        if target_broker_id is None:
            raise HTTPException(
                status_code=422,
                detail="broker_id required for superadmin",
            )
        return target_broker_id

    if not user_broker_id:
        raise HTTPException(status_code=403, detail="No broker associated with user")

    if target_broker_id and target_broker_id != user_broker_id:
        raise HTTPException(status_code=403, detail="Access denied to this broker's data")

    return user_broker_id


def _period_dates(period: str) -> tuple[datetime, datetime]:
    """Return (start_dt, end_dt) in UTC for the requested period."""
    now = datetime.now(timezone.utc)
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=7)
    elif period == "month":
        start = now - timedelta(days=30)
    elif period == "quarter":
        start = now - timedelta(days=90)
    else:
        raise HTTPException(status_code=422, detail=f"Invalid period: {period!r}. Use today/week/month/quarter")
    return start, now


# ── Summary endpoint ──────────────────────────────────────────────────────────

@router.get("/summary")
async def cost_summary(
    period: str = Query("month", description="today | week | month | quarter"),
    broker_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Aggregated cost summary for a broker over a time period.

    Returns:
    - total_cost_usd
    - cost_by_provider: {gemini: x, claude: y, ...}
    - cost_by_call_type: {qualification: x, chat_response: y, ...}
    - total_calls, fallback_rate, avg_latency_ms
    - daily_alert: True if today's cost exceeds DAILY_COST_ALERT_USD
    - qualified_leads: how many distinct leads had a "qualification" call
    - cost_per_qualified_lead
    """
    effective_broker_id = _check_admin(current_user, broker_id)
    start_dt, end_dt = _period_dates(period)

    base_q = (
        select(LLMCall)
        .where(LLMCall.broker_id == effective_broker_id)
        .where(LLMCall.created_at >= start_dt)
        .where(LLMCall.created_at <= end_dt)
    )
    result = await db.execute(base_q)
    rows = result.scalars().all()

    total_cost = sum((r.estimated_cost_usd or 0.0) for r in rows)
    total_calls = len(rows)
    fallback_calls = sum(1 for r in rows if r.used_fallback)
    avg_latency = (
        sum((r.latency_ms or 0) for r in rows) / total_calls if total_calls else 0
    )

    # Cost breakdown by provider
    cost_by_provider: dict[str, float] = {}
    for r in rows:
        p = r.provider or "unknown"
        cost_by_provider[p] = round(cost_by_provider.get(p, 0.0) + (r.estimated_cost_usd or 0.0), 8)

    # Cost breakdown by call type
    cost_by_call_type: dict[str, float] = {}
    for r in rows:
        ct = r.call_type or "unknown"
        cost_by_call_type[ct] = round(cost_by_call_type.get(ct, 0.0) + (r.estimated_cost_usd or 0.0), 8)

    # Qualified leads (distinct lead_ids that had a qualification call)
    qualified_lead_ids = {
        r.lead_id for r in rows if r.call_type == "qualification" and r.lead_id
    }
    qualified_leads = len(qualified_lead_ids)
    cost_per_qualified = (
        round(total_cost / qualified_leads, 6) if qualified_leads else None
    )

    # Daily alert: check today's cost
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_cost = sum(
        (r.estimated_cost_usd or 0.0)
        for r in rows
        if r.created_at and r.created_at >= today_start
    )
    alert_threshold = _alert_threshold()
    daily_alert = today_cost >= alert_threshold

    return {
        "broker_id": effective_broker_id,
        "period": period,
        "from": start_dt.isoformat(),
        "to": end_dt.isoformat(),
        "total_cost_usd": round(total_cost, 6),
        "total_calls": total_calls,
        "fallback_calls": fallback_calls,
        "fallback_rate": round(fallback_calls / total_calls, 3) if total_calls else 0.0,
        "avg_latency_ms": round(avg_latency, 1),
        "cost_by_provider": cost_by_provider,
        "cost_by_call_type": cost_by_call_type,
        "qualified_leads": qualified_leads,
        "cost_per_qualified_lead_usd": cost_per_qualified,
        "daily_cost_usd": round(today_cost, 6),
        "daily_alert": daily_alert,
        "daily_alert_threshold_usd": alert_threshold,
    }


# ── Daily breakdown ───────────────────────────────────────────────────────────

@router.get("/daily")
async def cost_daily(
    period: str = Query("month"),
    broker_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Day-by-day cost array suitable for a frontend chart."""
    effective_broker_id = _check_admin(current_user, broker_id)
    start_dt, end_dt = _period_dates(period)

    result = await db.execute(
        select(LLMCall)
        .where(LLMCall.broker_id == effective_broker_id)
        .where(LLMCall.created_at >= start_dt)
        .where(LLMCall.created_at <= end_dt)
        .order_by(LLMCall.created_at)
    )
    rows = result.scalars().all()

    # Aggregate by calendar date
    by_day: dict[str, float] = {}
    for r in rows:
        if r.created_at:
            day_str = r.created_at.strftime("%Y-%m-%d")
            by_day[day_str] = round(by_day.get(day_str, 0.0) + (r.estimated_cost_usd or 0.0), 8)

    # Fill zero-cost days between start and end
    current = start_dt.date()
    end_date = end_dt.date()
    daily_series = []
    while current <= end_date:
        day_str = current.strftime("%Y-%m-%d")
        daily_series.append({"date": day_str, "cost_usd": by_day.get(day_str, 0.0)})
        current += timedelta(days=1)

    return {
        "broker_id": effective_broker_id,
        "period": period,
        "daily": daily_series,
    }


# ── Outliers (most expensive conversations) ───────────────────────────────────

@router.get("/outliers")
async def cost_outliers(
    period: str = Query("month"),
    broker_id: Optional[int] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return top-N most expensive lead conversations in the period."""
    effective_broker_id = _check_admin(current_user, broker_id)
    start_dt, end_dt = _period_dates(period)

    result = await db.execute(
        select(
            LLMCall.lead_id,
            func.sum(LLMCall.estimated_cost_usd).label("total_cost"),
            func.count(LLMCall.id).label("call_count"),
            func.avg(LLMCall.latency_ms).label("avg_latency"),
        )
        .where(LLMCall.broker_id == effective_broker_id)
        .where(LLMCall.created_at >= start_dt)
        .where(LLMCall.created_at <= end_dt)
        .where(LLMCall.lead_id.is_not(None))
        .group_by(LLMCall.lead_id)
        .order_by(func.sum(LLMCall.estimated_cost_usd).desc())
        .limit(limit)
    )
    rows = result.all()

    return {
        "broker_id": effective_broker_id,
        "period": period,
        "outliers": [
            {
                "lead_id": r.lead_id,
                "total_cost_usd": round(float(r.total_cost or 0), 6),
                "call_count": r.call_count,
                "avg_latency_ms": round(float(r.avg_latency or 0), 1),
            }
            for r in rows
        ],
    }


# ── CSV export ────────────────────────────────────────────────────────────────

@router.get("/export")
async def cost_export_csv(
    period: str = Query("month"),
    broker_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export detailed llm_calls rows as CSV."""
    effective_broker_id = _check_admin(current_user, broker_id)
    start_dt, end_dt = _period_dates(period)

    result = await db.execute(
        select(LLMCall)
        .where(LLMCall.broker_id == effective_broker_id)
        .where(LLMCall.created_at >= start_dt)
        .where(LLMCall.created_at <= end_dt)
        .order_by(LLMCall.created_at)
    )
    rows = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "broker_id", "lead_id", "provider", "model", "call_type",
        "used_fallback", "input_tokens", "output_tokens",
        "estimated_cost_usd", "latency_ms", "error", "created_at",
    ])
    for r in rows:
        writer.writerow([
            r.id, r.broker_id, r.lead_id, r.provider, r.model, r.call_type,
            r.used_fallback, r.input_tokens, r.output_tokens,
            r.estimated_cost_usd, r.latency_ms, r.error or "",
            r.created_at.isoformat() if r.created_at else "",
        ])

    output.seek(0)
    filename = f"llm_costs_broker{effective_broker_id}_{period}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── By-broker (SUPERADMIN only) ─────────────────────────────────────────────

def _require_superadmin(current_user: dict) -> None:
    role = (current_user.get("role") or "").upper()
    if role != "SUPERADMIN":
        raise HTTPException(status_code=403, detail="Superadmin only")


@router.get("/by-broker")
async def cost_by_broker(
    period: str = Query("month", description="today | week | month | quarter"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Cost aggregated by broker. SUPERADMIN only.
    Returns list of brokers with total_cost_usd, total_calls, leads_qualified, cost_per_lead.
    """
    _require_superadmin(current_user)
    start_dt, end_dt = _period_dates(period)

    # Aggregate by broker_id from llm_calls
    agg = (
        select(
            LLMCall.broker_id,
            func.coalesce(func.sum(LLMCall.estimated_cost_usd), 0).label("total_cost_usd"),
            func.count(LLMCall.id).label("total_calls"),
            func.count(func.distinct(LLMCall.lead_id)).label("leads_count"),
        )
        .where(LLMCall.created_at >= start_dt)
        .where(LLMCall.created_at <= end_dt)
        .where(LLMCall.broker_id.is_not(None))
        .group_by(LLMCall.broker_id)
    )
    result = await db.execute(agg)
    rows = result.all()

    # Qualified leads per broker: distinct lead_id with at least one qualification call
    qualified_subq = (
        select(LLMCall.broker_id, LLMCall.lead_id)
        .where(LLMCall.call_type == "qualification")
        .where(LLMCall.lead_id.is_not(None))
        .where(LLMCall.created_at >= start_dt)
        .where(LLMCall.created_at <= end_dt)
        .distinct()
    )
    result_q = await db.execute(qualified_subq)
    qualified_pairs = result_q.all()
    qualified_by_broker: dict[int, set] = {}
    for b_id, lead_id in qualified_pairs:
        if b_id not in qualified_by_broker:
            qualified_by_broker[b_id] = set()
        qualified_by_broker[b_id].add(lead_id)

    # Broker names
    broker_ids = [r.broker_id for r in rows]
    brokers_result = await db.execute(select(Broker).where(Broker.id.in_(broker_ids)))
    brokers = { b.id: b for b in brokers_result.scalars().all() }

    brokers_list = []
    for r in rows:
        total_cost = round(float(r.total_cost_usd or 0), 6)
        total_calls = r.total_calls or 0
        qualified = len(qualified_by_broker.get(r.broker_id, set()))
        cost_per_lead = round(total_cost / qualified, 6) if qualified else None
        b = brokers.get(r.broker_id)
        broker_name = b.name if b else None
        brokers_list.append({
            "broker_id": r.broker_id,
            "broker_name": broker_name,
            "total_cost_usd": total_cost,
            "total_calls": total_calls,
            "leads_qualified": qualified,
            "cost_per_lead": cost_per_lead,
        })

    # Sort by total_cost_usd descending
    brokers_list.sort(key=lambda x: x["total_cost_usd"], reverse=True)

    return {"period": period, "brokers": brokers_list}


# ── Paginated calls ──────────────────────────────────────────────────────────

@router.get("/calls")
async def cost_calls(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    provider: Optional[str] = Query(None),
    broker_id: Optional[int] = Query(None),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    lead_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None, description="success | error"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Paginated list of LLM calls with optional filters.
    """
    effective_broker_id = _check_admin(current_user, broker_id)

    base = select(LLMCall).where(LLMCall.broker_id == effective_broker_id)
    if provider:
        base = base.where(LLMCall.provider == provider)
    if lead_id is not None:
        base = base.where(LLMCall.lead_id == lead_id)
    if status == "success":
        base = base.where(LLMCall.error.is_(None))
    elif status == "error":
        base = base.where(LLMCall.error.is_not(None))
    if from_date:
        try:
            start = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            base = base.where(LLMCall.created_at >= start)
        except ValueError:
            pass
    if to_date:
        try:
            end = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            base = base.where(LLMCall.created_at <= end)
        except ValueError:
            pass

    count_q = select(func.count(LLMCall.id)).select_from(LLMCall).where(
        LLMCall.broker_id == effective_broker_id
    )
    if provider:
        count_q = count_q.where(LLMCall.provider == provider)
    if lead_id is not None:
        count_q = count_q.where(LLMCall.lead_id == lead_id)
    if status == "success":
        count_q = count_q.where(LLMCall.error.is_(None))
    elif status == "error":
        count_q = count_q.where(LLMCall.error.is_not(None))
    if from_date:
        try:
            start = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            count_q = count_q.where(LLMCall.created_at >= start)
        except ValueError:
            pass
    if to_date:
        try:
            end = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            count_q = count_q.where(LLMCall.created_at <= end)
        except ValueError:
            pass
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    base = base.order_by(LLMCall.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(base)
    rows = result.scalars().all()

    items = [
        {
            "id": r.id,
            "broker_id": r.broker_id,
            "lead_id": r.lead_id,
            "provider": r.provider,
            "model": r.model,
            "call_type": r.call_type,
            "used_fallback": r.used_fallback,
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
            "estimated_cost_usd": r.estimated_cost_usd,
            "latency_ms": r.latency_ms,
            "error": r.error,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

    return {"items": items, "total": total, "page": page, "limit": limit}
