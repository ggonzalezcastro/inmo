"""
Deals REST router.

Endpoints:
  POST   /api/deals                          — create deal
  GET    /api/deals                          — list deals
  GET    /api/deals/{deal_id}                — deal detail (docs + required slots)
  POST   /api/deals/{deal_id}/transition     — advance stage
  POST   /api/deals/{deal_id}/cancel         — cancel deal
  POST   /api/deals/{deal_id}/bank-review    — set bank review decision
  POST   /api/deals/{deal_id}/jefatura-review — set jefatura review decision
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.permissions import Permissions
from app.models.deal import Deal
from app.models.deal_document import DealDocument
from app.models.lead import Lead
from app.models.project import Project
from app.models.property import Property
from app.schemas.deal import (
    BankReviewRequest,
    DealCancelRequest,
    DealCreate,
    DealDetail,
    DealDocumentRead,
    DealRead,
    DealStageTransitionRequest,
    JefaturaReviewRequest,
    SlotRequirementRead,
)
from app.core.websocket_manager import ws_manager
from app.services.deals.documents import DealDocumentService
from app.services.deals.effects import apply_transition_effects
from app.services.deals.exceptions import DealError
from app.services.deals.service import DealService
from app.services.deals.slots import get_all_required_slots_for_promesa
from app.services.deals.state_machine import transition

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deals", tags=["deals"])


def _base_url(request: Request) -> str:
    return getattr(settings, "BASE_URL", None) or str(request.base_url).rstrip("/")


async def _enrich(db: AsyncSession, deal_read: DealRead, deal: Deal) -> DealRead:
    """Populate lead_name and property_label by joining Lead/Property/Project."""
    lead = await db.get(Lead, deal.lead_id)
    prop = await db.get(Property, deal.property_id)

    if lead:
        deal_read.lead_name = lead.name or lead.phone

    if prop:
        label_parts: list[str] = []
        if prop.project_id:
            project = await db.get(Project, prop.project_id)
            if project and project.name:
                label_parts.append(project.name)
        if prop.name:
            label_parts.append(prop.name)
        elif prop.codigo:
            label_parts.append(prop.codigo)
        deal_read.property_label = " ".join(label_parts) if label_parts else None

    return deal_read


# ── POST /api/deals — Create deal ────────────────────────────────────────────

@router.post("", response_model=DealRead, status_code=201)
async def create_deal(
    body: DealCreate,
    request: Request,
    current_user: dict = Depends(Permissions.require_write_access),
    db: AsyncSession = Depends(get_db),
):
    broker_id: int = current_user["broker_id"]
    _raw_uid = current_user.get("id") or current_user.get("user_id")
    user_id: int | None = int(_raw_uid) if _raw_uid is not None else None
    try:
        deal = await DealService.create(
            db,
            broker_id=broker_id,
            lead_id=body.lead_id,
            property_id=body.property_id,
            delivery_type=body.delivery_type,
            created_by_user_id=user_id,
        )
    except DealError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    await db.commit()
    await db.refresh(deal)
    await ws_manager.broadcast(
        broker_id=broker_id,
        event="property_status_changed",
        data={"property_id": body.property_id, "status": "reserved", "deal_id": deal.id},
    )
    return await _enrich(db, DealRead.model_validate(deal), deal)


# ── GET /api/deals — List deals ───────────────────────────────────────────────

@router.get("", response_model=list[DealRead])
async def list_deals(
    lead_id: Optional[int] = Query(None),
    property_id: Optional[int] = Query(None),
    stage: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    broker_id: int = current_user["broker_id"]
    try:
        deals = await DealService.list_deals(
            db,
            broker_id=broker_id,
            lead_id=lead_id,
            property_id=property_id,
            stage=stage,
            limit=limit,
            offset=offset,
        )
    except DealError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    result = []
    for d in deals:
        result.append(await _enrich(db, DealRead.model_validate(d), d))
    return result


# ── GET /api/deals/{deal_id} — Deal detail ────────────────────────────────────

@router.get("/{deal_id}", response_model=DealDetail)
async def get_deal(
    deal_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    broker_id: int = current_user["broker_id"]
    try:
        deal = await DealService.get(db, deal_id=deal_id, broker_id=broker_id)
    except DealError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # Load documents
    result = await db.execute(
        select(DealDocument).where(DealDocument.deal_id == deal.id)
    )
    docs_orm = list(result.scalars().all())

    base = _base_url(request)
    docs_read: list[DealDocumentRead] = []
    for doc in docs_orm:
        doc_schema = DealDocumentRead.model_validate(doc)
        doc_schema.download_url = DealDocumentService.build_download_url(doc, broker_id, base)
        docs_read.append(doc_schema)

    # Compute required slots with upload/approval counts
    slot_reqs = get_all_required_slots_for_promesa(deal.delivery_type)
    required_slots: list[SlotRequirementRead] = []
    for req in slot_reqs:
        uploaded = sum(
            1 for d in docs_orm
            if d.slot == req.slot_key and d.status in ("recibido", "aprobado")
        )
        approved = sum(
            1 for d in docs_orm
            if d.slot == req.slot_key and d.status == "aprobado"
        )
        required_slots.append(
            SlotRequirementRead(
                slot_key=req.slot_key,
                label=req.definition.label,
                required_for_stage=req.definition.required_for_stage,
                max_count=req.definition.max_count,
                supports_co_titular=req.definition.supports_co_titular,
                optional=req.definition.optional,
                required=req.required,
                mime_whitelist=list(req.definition.mime_whitelist),
                uploaded_count=uploaded,
                approved_count=approved,
            )
        )

    enriched_base = await _enrich(db, DealRead.model_validate(deal), deal)
    detail = DealDetail(
        **enriched_base.model_dump(),
        documents=docs_read,
        required_slots=required_slots,
    )
    return detail


# ── POST /api/deals/{deal_id}/transition — Advance stage ─────────────────────

@router.post("/{deal_id}/transition", response_model=DealRead)
async def advance_stage(
    deal_id: int,
    body: DealStageTransitionRequest,
    current_user: dict = Depends(Permissions.require_write_access),
    db: AsyncSession = Depends(get_db),
):
    broker_id: int = current_user["broker_id"]
    _raw_uid = current_user.get("id") or current_user.get("user_id")
    user_id: int | None = int(_raw_uid) if _raw_uid is not None else None
    try:
        deal = await DealService.get(db, deal_id=deal_id, broker_id=broker_id)
        from_stage = deal.stage

        cancellation_reason: str | None = None
        if body.to_stage == "cancelado":
            raise HTTPException(
                status_code=422,
                detail="Usa el endpoint /cancel para cancelar un deal.",
            )

        await transition(deal, body.to_stage, db)
        await apply_transition_effects(deal, from_stage, body.to_stage, db, actor_user_id=user_id)
    except DealError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    await db.commit()
    await db.refresh(deal)
    return await _enrich(db, DealRead.model_validate(deal), deal)


# ── POST /api/deals/{deal_id}/cancel — Cancel deal ───────────────────────────

@router.post("/{deal_id}/cancel", response_model=DealRead)
async def cancel_deal(
    deal_id: int,
    body: DealCancelRequest,
    current_user: dict = Depends(Permissions.require_write_access),
    db: AsyncSession = Depends(get_db),
):
    broker_id: int = current_user["broker_id"]
    _raw_uid = current_user.get("id") or current_user.get("user_id")
    user_id: int | None = int(_raw_uid) if _raw_uid is not None else None
    try:
        deal = await DealService.get(db, deal_id=deal_id, broker_id=broker_id)
        from_stage = deal.stage
        await transition(
            deal,
            "cancelado",
            db,
            cancellation_reason=body.reason,
            cancellation_notes=body.notes,
        )
        await apply_transition_effects(deal, from_stage, "cancelado", db, actor_user_id=user_id)
    except DealError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    await db.commit()
    await db.refresh(deal)
    return await _enrich(db, DealRead.model_validate(deal), deal)


# ── POST /api/deals/{deal_id}/bank-review — Bank review decision ─────────────

@router.post("/{deal_id}/bank-review", response_model=DealRead)
async def set_bank_review(
    deal_id: int,
    body: BankReviewRequest,
    current_user: dict = Depends(Permissions.require_write_access),
    db: AsyncSession = Depends(get_db),
):
    broker_id: int = current_user["broker_id"]
    try:
        deal = await DealService.get(db, deal_id=deal_id, broker_id=broker_id)
    except DealError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    deal.bank_review_status = body.decision
    if body.decision == "aprobado":
        deal.bank_decision_at = datetime.now(timezone.utc)
    db.add(deal)
    await db.commit()
    await db.refresh(deal)
    return await _enrich(db, DealRead.model_validate(deal), deal)


# ── POST /api/deals/{deal_id}/jefatura-review — Jefatura review ──────────────

@router.post("/{deal_id}/jefatura-review", response_model=DealRead)
async def set_jefatura_review(
    deal_id: int,
    body: JefaturaReviewRequest,
    current_user: dict = Depends(Permissions.require_write_access),
    db: AsyncSession = Depends(get_db),
):
    broker_id: int = current_user["broker_id"]
    try:
        deal = await DealService.get(db, deal_id=deal_id, broker_id=broker_id)
    except DealError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    if not deal.jefatura_review_required:
        raise HTTPException(
            status_code=422,
            detail="Este deal no requiere revisión de jefatura.",
        )

    deal.jefatura_review_status = body.decision
    deal.jefatura_review_notes = body.notes
    db.add(deal)
    await db.commit()
    await db.refresh(deal)
    return await _enrich(db, DealRead.model_validate(deal), deal)
