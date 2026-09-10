"""HTTP endpoints for lead notes, executive tasks and task inbox."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.schemas.lead_follow_up import (
    LeadAdvisoryCreate,
    LeadAdvisoryListResponse,
    LeadAdvisoryResponse,
    LeadNoteCreate,
    LeadNoteListResponse,
    LeadNoteResponse,
    LeadTaskCreate,
    LeadTaskListResponse,
    LeadTaskResponse,
    LeadTaskUpdate,
    TaskStatus,
)
from app.services.leads.follow_up_service import LeadFollowUpService


lead_follow_up_router = APIRouter()
tasks_router = APIRouter()


@lead_follow_up_router.get(
    "/{lead_id}/advisories",
    response_model=LeadAdvisoryListResponse,
)
async def list_lead_advisories(
    lead_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    advisories, total = await LeadFollowUpService.list_advisories(
        db, lead_id, current_user, skip=skip, limit=limit
    )
    return LeadAdvisoryListResponse(
        data=advisories,
        total=total,
        skip=skip,
        limit=limit,
    )


@lead_follow_up_router.post(
    "/{lead_id}/advisories",
    response_model=LeadAdvisoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_lead_advisory(
    lead_id: int,
    payload: LeadAdvisoryCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LeadFollowUpService.create_advisory(
        db, lead_id, payload, current_user
    )


@lead_follow_up_router.get("/{lead_id}/notes", response_model=LeadNoteListResponse)
async def list_lead_notes(
    lead_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notes, total = await LeadFollowUpService.list_notes(
        db, lead_id, current_user, skip=skip, limit=limit
    )
    return LeadNoteListResponse(data=notes, total=total, skip=skip, limit=limit)


@lead_follow_up_router.post(
    "/{lead_id}/notes",
    response_model=LeadNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_lead_note(
    lead_id: int,
    payload: LeadNoteCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LeadFollowUpService.create_note(db, lead_id, payload, current_user)


@lead_follow_up_router.get("/{lead_id}/tasks", response_model=LeadTaskListResponse)
async def list_lead_tasks(
    lead_id: int,
    task_status: Optional[TaskStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks, total = await LeadFollowUpService.list_tasks(
        db,
        current_user,
        lead_id=lead_id,
        task_status=task_status,
        skip=skip,
        limit=limit,
    )
    return LeadTaskListResponse(data=tasks, total=total, skip=skip, limit=limit)


@lead_follow_up_router.post(
    "/{lead_id}/tasks",
    response_model=LeadTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_lead_task(
    lead_id: int,
    payload: LeadTaskCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LeadFollowUpService.create_task(db, lead_id, payload, current_user)


@tasks_router.get("", response_model=LeadTaskListResponse)
async def list_tasks(
    task_status: Optional[TaskStatus] = Query(None, alias="status"),
    assigned_to: Optional[int] = Query(None),
    lead_id: Optional[int] = Query(None),
    broker_id: Optional[int] = Query(None),
    overdue: Optional[bool] = Query(None),
    due_from: Optional[datetime] = Query(None),
    due_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tasks, total = await LeadFollowUpService.list_tasks(
        db,
        current_user,
        lead_id=lead_id,
        task_status=task_status,
        assigned_to=assigned_to,
        broker_id=broker_id,
        overdue=overdue,
        due_from=due_from,
        due_to=due_to,
        skip=skip,
        limit=limit,
    )
    return LeadTaskListResponse(data=tasks, total=total, skip=skip, limit=limit)


@tasks_router.get("/reminders/pending", response_model=list[LeadTaskResponse])
async def list_pending_reminders(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LeadFollowUpService.list_pending_reminders(
        db, current_user, limit=limit
    )


@tasks_router.get("/metrics/summary")
async def get_task_metrics(
    assigned_to: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LeadFollowUpService.get_task_metrics(
        db, current_user, assigned_to=assigned_to
    )


@tasks_router.get("/{task_id}", response_model=LeadTaskResponse)
async def get_task(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LeadFollowUpService.get_task(db, task_id, current_user)


@tasks_router.patch("/{task_id}", response_model=LeadTaskResponse)
async def update_task(
    task_id: int,
    payload: LeadTaskUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LeadFollowUpService.update_task(db, task_id, payload, current_user)


@tasks_router.post("/{task_id}/complete", response_model=LeadTaskResponse)
async def complete_task(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LeadFollowUpService.set_completed(
        db, task_id, current_user, completed=True
    )


@tasks_router.post("/{task_id}/start", response_model=LeadTaskResponse)
async def start_task(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LeadFollowUpService.set_in_progress(db, task_id, current_user)


@tasks_router.post("/{task_id}/reopen", response_model=LeadTaskResponse)
async def reopen_task(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await LeadFollowUpService.set_completed(
        db, task_id, current_user, completed=False
    )


@tasks_router.post("/{task_id}/reminder/ack", status_code=status.HTTP_204_NO_CONTENT)
async def acknowledge_reminder(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await LeadFollowUpService.acknowledge_reminder(db, task_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@tasks_router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await LeadFollowUpService.delete_task(db, task_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
