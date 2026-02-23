"""
Admin endpoints for Dead Letter Queue management (TASK-029).

Endpoints:
    GET  /api/v1/admin/tasks/failed        — list DLQ entries
    POST /api/v1/admin/tasks/{id}/retry    — requeue a specific entry
    DELETE /api/v1/admin/tasks/{id}        — discard a specific entry
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_db
from app.middleware.auth import get_current_user
from app.tasks.dlq import DLQManager

router = APIRouter()


def _require_admin(current_user: dict) -> None:
    role = (current_user.get("role") or "").upper()
    if role not in ("ADMIN", "SUPERADMIN"):
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/failed")
async def list_failed_tasks(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """
    List tasks currently in the Dead Letter Queue.

    Returns entries newest-first. Each entry includes:
    - id, task_name, args, kwargs, exception, retries, failed_at
    """
    _require_admin(current_user)
    entries = await DLQManager.list_failed(offset=offset, limit=limit)
    total = await DLQManager.count()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": entries,
    }


@router.post("/{entry_id}/retry", status_code=202)
async def retry_failed_task(
    entry_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Requeue a DLQ entry back to Celery and remove it from the DLQ.

    Returns 404 if the entry is not found.
    """
    _require_admin(current_user)
    ok = await DLQManager.retry(entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"DLQ entry {entry_id!r} not found")
    return {"status": "requeued", "id": entry_id}


@router.delete("/{entry_id}", status_code=200)
async def discard_failed_task(
    entry_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Permanently remove a DLQ entry without retrying.

    Returns 404 if the entry is not found.
    """
    _require_admin(current_user)
    ok = await DLQManager.delete(entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"DLQ entry {entry_id!r} not found")
    return {"status": "discarded", "id": entry_id}
