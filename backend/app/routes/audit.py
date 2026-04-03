"""
Super admin endpoint for querying the audit log.
Mounted at: /api/v1/admin/audit-log
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.permissions import Permissions
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter()


@router.get("")
async def list_audit_log(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    broker_id: Optional[int] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(Permissions.require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Paginated audit log. Only accessible by SUPERADMIN.
    """
    offset = (page - 1) * limit
    filters = []

    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if action:
        filters.append(AuditLog.action == action)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if broker_id is not None:
        filters.append(AuditLog.broker_id == broker_id)
    if from_date:
        filters.append(AuditLog.timestamp >= from_date)
    if to_date:
        filters.append(AuditLog.timestamp <= to_date)

    where_clause = and_(*filters) if filters else True

    # Count
    count_result = await db.execute(
        select(func.count(AuditLog.id)).where(where_clause)
    )
    total = count_result.scalar() or 0

    # Items with user email joined
    result = await db.execute(
        select(AuditLog, User.email)
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(where_clause)
        .order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()

    items = []
    for log, email in rows:
        items.append({
            "id": log.id,
            "user_id": log.user_id,
            "user_email": email,
            "broker_id": log.broker_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "changes": log.changes,
            "ip_address": log.ip_address,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        })

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": items,
    }
