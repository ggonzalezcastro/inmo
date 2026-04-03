"""
Utility for creating AuditLog entries.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def log_audit(
    db: AsyncSession,
    *,
    user_id: Optional[int],
    broker_id: Optional[int] = None,
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    changes: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    """
    Insert an AuditLog row. Failures are logged but never raised —
    audit logging must not break the main request flow.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            broker_id=broker_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(entry)
        await db.flush()
    except Exception as exc:
        logger.warning("audit log failed: %s", exc)
