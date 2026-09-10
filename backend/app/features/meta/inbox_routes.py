"""Authenticated unified-inbox endpoints for Meta conversations."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.schemas.meta_inbox import (
    MetaAssignmentConflictResolve,
    MetaAssignmentConflictResponse,
    MetaAIDraftRequest,
    MetaAIDraftResponse,
    MetaAISummaryResponse,
    MetaAITaskApprove,
    MetaAITaskSuggestion,
    MetaInboxConversationDetail,
    MetaInboxConversationPage,
    MetaInboxMessagePage,
    MetaInboxSendRequest,
    MetaInboxSendResponse,
)
from app.services.meta.inbox import (
    MetaAssignmentConflictService,
    MetaInboxService,
    broker_id_from_claims,
    user_id_from_claims,
)
from app.services.meta.outbound import MetaOutboundError, MetaOutboundService
from app.services.meta.ai_assistance import MetaAIAssistanceService

router = APIRouter()


@router.get("/inbox/conversations", response_model=MetaInboxConversationPage)
async def list_meta_conversations(
    limit: int = Query(30, ge=1, le=100),
    cursor: Optional[str] = None,
    channel: Optional[str] = None,
    asset_id: Optional[int] = None,
    assigned_user_id: Optional[int] = None,
    pipeline_stage: Optional[str] = None,
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = Query(None, max_length=120),
    from_at: Optional[datetime] = None,
    to_at: Optional[datetime] = None,
    conflict_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await MetaInboxService.list_conversations(
        db,
        current_user=current_user,
        limit=limit,
        cursor=cursor,
        channel=channel,
        asset_id=asset_id,
        assigned_user_id=assigned_user_id,
        pipeline_stage=pipeline_stage,
        project_id=project_id,
        status=status,
        search=search,
        from_at=from_at,
        to_at=to_at,
        conflict_only=conflict_only,
    )


@router.get(
    "/inbox/conversations/{conversation_id}",
    response_model=MetaInboxConversationDetail,
)
async def get_meta_conversation(
    conversation_id: int,
    message_limit: int = Query(60, ge=1, le=200),
    before_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return {
        "conversation": await MetaInboxService.item_for_conversation(
            db,
            conversation_id=conversation_id,
            current_user=current_user,
        ),
        "messages": await MetaInboxService.messages(
            db,
            conversation_id=conversation_id,
            current_user=current_user,
            limit=message_limit,
            before_id=before_id,
        ),
    }


@router.get(
    "/inbox/conversations/{conversation_id}/messages",
    response_model=MetaInboxMessagePage,
)
async def get_meta_messages(
    conversation_id: int,
    limit: int = Query(60, ge=1, le=200),
    before_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await MetaInboxService.messages(
        db,
        conversation_id=conversation_id,
        current_user=current_user,
        limit=limit,
        before_id=before_id,
    )


@router.post(
    "/inbox/conversations/{conversation_id}/messages",
    response_model=MetaInboxSendResponse,
)
async def send_meta_message(
    conversation_id: int,
    body: MetaInboxSendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    await MetaInboxService.assert_access(
        db,
        conversation_id=conversation_id,
        current_user=current_user,
        allow_superadmin_send=False,
    )
    try:
        result = await MetaOutboundService.send_for_conversation(
            db,
            broker_id=broker_id_from_claims(current_user),
            conversation_id=conversation_id,
            message_text=body.text,
            sent_by_user_id=user_id_from_claims(current_user),
            reply_to_external_id=body.reply_to_external_id,
            template_name=body.template_name,
            template_language=body.template_language,
            template_components=body.template_components,
            generation_mode=body.generation_mode,
            media_url=str(body.media_url) if body.media_url else None,
            media_type=body.media_type,
        )
    except MetaOutboundError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    if not result.provider_result.success:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "META_SEND_FAILED",
                "message": "Meta rechazó el envío",
                "message_id": result.message.id,
            },
        )
    page = await MetaInboxService.messages(
        db,
        conversation_id=conversation_id,
        current_user=current_user,
        limit=1,
        before_id=None,
    )
    return {"ok": True, "message": page["items"][-1]}


@router.post("/inbox/conversations/{conversation_id}/read")
async def mark_meta_conversation_read(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    message_id = await MetaInboxService.mark_read(
        db,
        conversation_id=conversation_id,
        current_user=current_user,
    )
    return {"ok": True, "last_read_message_id": message_id}


@router.get(
    "/inbox/conversations/{conversation_id}/ai/summary",
    response_model=MetaAISummaryResponse,
)
async def summarize_meta_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await MetaAIAssistanceService.summary(
        db,
        conversation_id=conversation_id,
        current_user=current_user,
    )


@router.post(
    "/inbox/conversations/{conversation_id}/ai/draft",
    response_model=MetaAIDraftResponse,
)
async def draft_meta_reply(
    conversation_id: int,
    body: MetaAIDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await MetaAIAssistanceService.draft(
        db,
        conversation_id=conversation_id,
        current_user=current_user,
        instruction=body.instruction,
    )


@router.post(
    "/inbox/conversations/{conversation_id}/ai/task-suggestion",
    response_model=MetaAITaskSuggestion,
)
async def suggest_meta_task(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await MetaAIAssistanceService.task_suggestion(
        db,
        conversation_id=conversation_id,
        current_user=current_user,
    )


@router.post("/inbox/conversations/{conversation_id}/ai/task-suggestion/approve")
async def approve_meta_task_suggestion(
    conversation_id: int,
    body: MetaAITaskApprove,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, lead = await MetaInboxService.assert_access(
        db,
        conversation_id=conversation_id,
        current_user=current_user,
        allow_superadmin_send=False,
    )
    if body.evidence_message_id is not None:
        from app.models.chat_message import ChatMessage
        from sqlalchemy import select

        evidence = await db.scalar(
            select(ChatMessage.id).where(
                ChatMessage.id == body.evidence_message_id,
                ChatMessage.broker_id == lead.broker_id,
                ChatMessage.conversation_id == conversation_id,
            )
        )
        if evidence is None:
            raise HTTPException(status_code=422, detail="El mensaje de evidencia no pertenece a la conversación")
    from app.schemas.lead_follow_up import LeadTaskCreate
    from app.services.leads.follow_up_service import LeadFollowUpService

    task = await LeadFollowUpService.create_task(
        db,
        lead.id,
        LeadTaskCreate(
            title=body.title,
            assigned_to=body.assigned_to,
            due_at=body.due_at,
            reminder_minutes_before=body.reminder_minutes_before,
        ),
        current_user,
    )
    if body.evidence_message_id is not None:
        from datetime import timezone
        from app.models.activity_log import ActivityLog

        db.add(ActivityLog(
            lead_id=lead.id,
            action_type="lead_task_ai_suggestion_approved",
            details={
                "task_id": task.id,
                "conversation_id": conversation_id,
                "evidence_message_id": body.evidence_message_id,
                "approved_by": user_id_from_claims(current_user),
            },
            timestamp=datetime.now(timezone.utc),
        ))
        await db.commit()
    return {"ok": True, "task": task}


@router.get(
    "/assignment-conflicts",
    response_model=list[MetaAssignmentConflictResponse],
)
async def list_meta_assignment_conflicts(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await MetaAssignmentConflictService.list_open(db, current_user)


@router.post(
    "/assignment-conflicts/{conflict_id}/resolve",
    response_model=MetaAssignmentConflictResponse,
)
async def resolve_meta_assignment_conflict(
    conflict_id: int,
    body: MetaAssignmentConflictResolve,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await MetaAssignmentConflictService.resolve(
        db,
        conflict_id=conflict_id,
        resolution=body.resolution,
        assigned_user_id=body.assigned_user_id,
        current_user=current_user,
    )
