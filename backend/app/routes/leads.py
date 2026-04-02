from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import csv
import io


from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.permissions import Permissions
from app.services.leads import LeadService, ScoringService
from app.services.pipeline import PipelineService
from app.schemas.lead import LeadCreate, LeadUpdate, LeadResponse, LeadDetailResponse
from app.core.encryption import decrypt_metadata_fields
from sqlalchemy.future import select
from app.models.lead import Lead
from app.models.user import User


router = APIRouter()


def _safe_metadata(raw) -> dict:
    """Return a decrypted, plain-dict version of lead_metadata safe for API responses."""
    if not isinstance(raw, dict):
        try:
            raw = dict(raw) if raw and hasattr(raw, '__dict__') else {}
        except (TypeError, ValueError):
            raw = {}
    return decrypt_metadata_fields(raw) or {}


def _build_lead_response(lead: Lead, meta: dict) -> LeadResponse:
    """Build a LeadResponse from a Lead ORM object and pre-decrypted metadata."""
    return LeadResponse(
        id=lead.id,
        phone=lead.phone,
        name=lead.name,
        email=lead.email,
        tags=lead.tags if lead.tags else [],
        metadata=meta,
        status=lead.status,
        lead_score=lead.lead_score,
        pipeline_stage=lead.pipeline_stage,
        last_contacted=lead.last_contacted,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


@router.get("", response_model=dict)
async def list_leads(
    status: str = Query(""),
    min_score: float = Query(0),
    max_score: float = Query(100),
    search: str = Query(""),
    pipeline_stage: str = Query(""),
    dicom_status: str = Query("", description="Filter by DICOM status: clean, has_debt, unknown"),
    created_from: str = Query("", description="ISO date string, e.g. 2026-01-01"),
    created_to: str = Query("", description="ISO date string, e.g. 2026-12-31"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all leads with filters - filtered by user role and DB-level where possible.

    Note: dicom_status filtering is applied in-memory after decryption because
    the field is encrypted at rest in lead_metadata.
    """
    try:
        user_role = current_user.get("role", "").upper()
        user_id = int(current_user.get("user_id"))
        broker_id = current_user.get("broker_id")

        # Build kwargs for service call — filter at DB level for all plain columns.
        # dicom_status is handled in-memory below since it's encrypted in JSONB.
        service_kwargs = dict(
            status=status or None,
            min_score=min_score,
            max_score=max_score,
            search=search or None,
            pipeline_stage=pipeline_stage or None,
            created_from=created_from or None,
            created_to=created_to or None,
        )

        if user_role == "AGENT":
            # Agents see only their own assigned leads
            service_kwargs["assigned_to"] = user_id
        else:
            # ADMIN sees their broker's leads; superadmin sees all
            if user_role == "ADMIN" and broker_id:
                service_kwargs["broker_id"] = broker_id

        if dicom_status:
            # Must fetch all matching records first, then filter by decrypted DICOM value.
            # We skip pagination at DB level and do it in-memory after decryption.
            leads, _ = await LeadService.get_leads(db, skip=0, limit=10_000, **service_kwargs)
            filtered_leads = []
            for lead in leads:
                meta = _safe_metadata(lead.lead_metadata)
                if meta.get("dicom_status") == dicom_status:
                    filtered_leads.append((lead, meta))
            total = len(filtered_leads)
            page = filtered_leads[skip: skip + limit]
            lead_responses = [_build_lead_response(lead, meta) for lead, meta in page]
        else:
            leads, total = await LeadService.get_leads(db, skip=skip, limit=limit, **service_kwargs)
            lead_responses = [_build_lead_response(lead, _safe_metadata(lead.lead_metadata)) for lead in leads]

        return {
            "data": [lr.model_dump(by_alias=True) for lr in lead_responses],
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{lead_id}", response_model=LeadDetailResponse)
async def get_lead(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get single lead"""
    lead = await LeadService.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Get recent activities
    from app.models.activity_log import ActivityLog
    from sqlalchemy import desc
    from sqlalchemy.future import select
    
    activities_result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.lead_id == lead_id)
        .order_by(desc(ActivityLog.timestamp))
        .limit(10)
    )
    activities = activities_result.scalars().all()
    
    lead_dict = {
        "id": lead.id,
        "phone": lead.phone,
        "name": lead.name,
        "email": lead.email,
        "tags": lead.tags if lead.tags else [],
        "metadata": _safe_metadata(lead.lead_metadata),
        "status": lead.status,
        "lead_score": lead.lead_score,
        "lead_score_components": lead.lead_score_components if lead.lead_score_components else {},
        "last_contacted": lead.last_contacted,
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
        "recent_activities": [
            {
                "id": act.id,
                "action_type": act.action_type,
                "details": act.details if act.details else {},
                "created_at": act.timestamp.isoformat() if act.timestamp else None
            }
            for act in activities
        ]
    }
    
    return LeadDetailResponse(**lead_dict)


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_data: LeadCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new lead"""
    try:
        lead = await LeadService.create_lead(db, lead_data)
        return _build_lead_response(lead, _safe_metadata(lead.lead_metadata))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: int,
    lead_data: LeadUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update lead"""
    try:
        lead = await LeadService.update_lead(db, lead_id, lead_data)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        return _build_lead_response(lead, _safe_metadata(lead.lead_metadata))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete lead"""
    try:
        await LeadService.delete_lead(db, lead_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{lead_id}/assign")
async def assign_lead(
    lead_id: int,
    request: dict,
    current_user: dict = Depends(Permissions.require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Assign lead to an agent (admin only)"""
    agent_id = request.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required")
    """Assign lead to an agent (admin only)"""
    # Get lead
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id)
    )
    lead = result.scalars().first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Verify agent belongs to same broker
    broker_id = current_user.get("broker_id")
    if broker_id:
        agent_result = await db.execute(
            select(User).where(User.id == agent_id, User.broker_id == broker_id)
        )
        agent = agent_result.scalars().first()
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found or doesn't belong to your broker")
    
    # Assign lead
    lead.assigned_to = agent_id
    await db.commit()
    await db.refresh(lead)
    
    # Log activity
    from app.services.shared import ActivityService
    await ActivityService.log_activity(
        db,
        lead_id=lead_id,
        action_type="assignment",
        details={
            "assigned_to": agent_id,
            "assigned_by": current_user.get("user_id")
        }
    )
    
    return {"message": "Lead assigned successfully", "lead_id": lead_id, "agent_id": agent_id}


@router.put("/{lead_id}/pipeline")
async def move_pipeline_stage(
    lead_id: int,
    request: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Move lead to a different pipeline stage"""
    stage = request.get("stage")
    if not stage:
        raise HTTPException(status_code=400, detail="stage is required")
    """Move lead to a different pipeline stage"""
    user_id = int(current_user.get("user_id"))
    
    lead = await PipelineService.move_lead_to_stage(
        db,
        lead_id,
        stage,
        reason=f"Manual update by user {user_id}"
    )
    
    return {
        "message": "Pipeline stage updated",
        "lead_id": lead_id,
        "new_stage": stage
    }


@router.post("/{lead_id}/recalculate")
async def recalculate_lead(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Recalculate lead score and qualification"""
    # Get lead first
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id)
    )
    lead = result.scalars().first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    # Recalculate score
    broker_id = lead.broker_id
    score_result = await ScoringService.calculate_lead_score(db, lead_id, broker_id)
    
    # Update score
    lead.lead_score = score_result["total"]
    lead.lead_score_components = {
        "base": score_result["base"],
        "behavior": score_result["behavior"],
        "engagement": score_result["engagement"],
        "stage": score_result["stage"],
        "financial": score_result.get("financial", 0),
        "penalties": score_result["penalties"]
    }
    
    # Recalculate qualification
    broker_id = lead.broker_id
    calificacion = await PipelineService.calcular_calificacion(db, lead, broker_id)
    metadata = lead.lead_metadata or {}
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["calificacion"] = calificacion
    lead.lead_metadata = metadata
    
    # Update pipeline stage
    await PipelineService.actualizar_pipeline_stage(db, lead)
    
    await db.commit()
    await db.refresh(lead)
    
    return {
        "message": "Lead recalculated",
        "lead_id": lead_id,
        "score": score_result["total"],
        "calificacion": calificacion,
        "pipeline_stage": lead.pipeline_stage
    }


@router.post("/bulk-import")
async def bulk_import_leads(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Import leads from CSV"""
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files accepted")
    
    contents = await file.read()
    reader = csv.DictReader(io.StringIO(contents.decode()))
    
    imported = 0
    duplicates = 0
    invalid = 0
    
    for row in reader:
        try:
            phone = row.get('phone', '').strip()
            name = row.get('name', '').strip()
            email = row.get('email', '').strip() or None
            tags_str = row.get('tags', '').strip()
            tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            
            lead_data = LeadCreate(
                phone=phone,
                name=name or None,
                email=email,
                tags=tags
            )
            
            await LeadService.create_lead(db, lead_data)
            imported += 1
        except ValueError:
            duplicates += 1
        except Exception:
            invalid += 1
    
    return {
        "imported": imported,
        "duplicates": duplicates,
        "invalid": invalid
    }

