"""
Plan limit enforcement — FastAPI dependencies that check broker usage against plan limits.

Usage:
    @router.post("/leads")
    async def create_lead(
        ...,
        _: None = Depends(check_lead_limit),
    ):
        ...

Limits are cached in Redis for 60 seconds to avoid per-request DB queries.
Returns HTTP 402 when a limit is exceeded.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get, cache_set, cache_delete
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.broker import Broker
from app.models.broker_plan import BrokerPlan
from app.models.lead import Lead
from app.models.user import User
from app.models.chat_message import ChatMessage

logger = logging.getLogger(__name__)

_CACHE_TTL = 60  # seconds


async def _get_plan(broker_id: int, db: AsyncSession) -> Optional[BrokerPlan]:
    """Load the broker's plan. Returns None if no plan is assigned (= unlimited)."""
    result = await db.execute(
        select(BrokerPlan)
        .join(Broker, Broker.plan_id == BrokerPlan.id)
        .where(Broker.id == broker_id, BrokerPlan.is_active == True)
    )
    return result.scalar_one_or_none()


def _cache_key(broker_id: int, metric: str) -> str:
    return f"plan_limit:{broker_id}:{metric}"


async def _get_cached_count(broker_id: int, metric: str) -> Optional[int]:
    val = await cache_get(_cache_key(broker_id, metric))
    return int(val) if val is not None else None


async def _set_cached_count(broker_id: int, metric: str, value: int) -> None:
    await cache_set(_cache_key(broker_id, metric), str(value), ttl_seconds=_CACHE_TTL)


async def invalidate_plan_cache(broker_id: int) -> None:
    """Call this after plan assignment or resource creation to clear cached counts."""
    for metric in ("leads", "users", "messages"):
        await cache_delete(_cache_key(broker_id, metric))


async def check_lead_limit(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Dependency: raise 402 if broker has reached their lead limit."""
    broker_id = current_user.get("broker_id")
    if not broker_id:
        return  # superadmins have no broker

    plan = await _get_plan(broker_id, db)
    if not plan or plan.max_leads is None:
        return  # no plan or unlimited

    count = await _get_cached_count(broker_id, "leads")
    if count is None:
        result = await db.execute(
            select(func.count(Lead.id)).where(Lead.broker_id == broker_id)
        )
        count = result.scalar() or 0
        await _set_cached_count(broker_id, "leads", count)

    if count >= plan.max_leads:
        raise HTTPException(
            status_code=402,
            detail=f"Límite de leads alcanzado ({plan.max_leads}). Actualiza tu plan para agregar más.",
        )


async def check_user_limit(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Dependency: raise 402 if broker has reached their user limit."""
    broker_id = current_user.get("broker_id")
    if not broker_id:
        return

    plan = await _get_plan(broker_id, db)
    if not plan or plan.max_users is None:
        return

    count = await _get_cached_count(broker_id, "users")
    if count is None:
        result = await db.execute(
            select(func.count(User.id)).where(
                User.broker_id == broker_id,
                User.is_active == True,
            )
        )
        count = result.scalar() or 0
        await _set_cached_count(broker_id, "users", count)

    if count >= plan.max_users:
        raise HTTPException(
            status_code=402,
            detail=f"Límite de usuarios alcanzado ({plan.max_users}). Actualiza tu plan.",
        )


async def check_message_limit(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Dependency: raise 402 if broker has reached their monthly message limit."""
    from datetime import datetime

    broker_id = current_user.get("broker_id")
    if not broker_id:
        return

    plan = await _get_plan(broker_id, db)
    if not plan or plan.max_messages_per_month is None:
        return

    count = await _get_cached_count(broker_id, "messages")
    if count is None:
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        result = await db.execute(
            select(func.count(ChatMessage.id)).where(
                ChatMessage.broker_id == broker_id,
                ChatMessage.created_at >= month_start,
            )
        )
        count = result.scalar() or 0
        await _set_cached_count(broker_id, "messages", count)

    if count >= plan.max_messages_per_month:
        raise HTTPException(
            status_code=402,
            detail=f"Límite mensual de mensajes alcanzado ({plan.max_messages_per_month:,}). Actualiza tu plan.",
        )
