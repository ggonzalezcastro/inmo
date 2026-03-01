"""
Pipeline routes for managing lead pipeline stages
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.pipeline import PipelineService
from pydantic import BaseModel
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class StageChangeRequest(BaseModel):
    new_stage: str
    reason: Optional[str] = None


@router.post("/leads/{lead_id}/move-stage")
async def move_lead_to_stage(
    lead_id: int,
    request: StageChangeRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Move a lead to a new pipeline stage"""
    
    try:
        lead = await PipelineService.move_lead_to_stage(
            db=db,
            lead_id=lead_id,
            new_stage=request.new_stage,
            reason=request.reason
        )
        
        return {
            "message": "Lead stage updated successfully",
            "lead_id": lead.id,
            "old_stage": None,  # Can be extracted from activity log
            "new_stage": lead.pipeline_stage,
            "stage_entered_at": lead.stage_entered_at.isoformat() if lead.stage_entered_at else None
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error moving lead stage: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/leads/{lead_id}/auto-advance")
async def auto_advance_lead_stage(
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Automatically advance lead stage if conditions are met"""
    
    try:
        lead = await PipelineService.auto_advance_stage(db=db, lead_id=lead_id)
        
        if lead:
            return {
                "message": "Lead stage advanced automatically",
                "lead_id": lead.id,
                "new_stage": lead.pipeline_stage,
                "stage_entered_at": lead.stage_entered_at.isoformat() if lead.stage_entered_at else None
            }
        else:
            return {
                "message": "No automatic advancement conditions met",
                "lead_id": lead_id
            }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error auto-advancing lead stage: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stages/{stage}/leads")
async def get_leads_by_stage(
    stage: str,
    treatment_type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get leads in a specific pipeline stage"""
    
    try:
        broker_id = current_user.get("broker_id")
        leads, total = await PipelineService.get_leads_by_stage(
            db=db,
            stage=stage,
            broker_id=broker_id,
            treatment_type=treatment_type,
            skip=skip,
            limit=limit
        )
        
        from app.schemas.lead import LeadResponse
        
        # Convert leads to dict format, ensuring metadata is a dict
        lead_responses = []
        for lead in leads:
            lead_dict = {
                "id": lead.id,
                "phone": lead.phone,
                "name": lead.name,
                "email": lead.email,
                "tags": lead.tags or [],
                "status": lead.status,
                "lead_score": lead.lead_score or 0.0,
                "last_contacted": lead.last_contacted,
                "created_at": lead.created_at,
                "updated_at": lead.updated_at,
                "metadata": lead.lead_metadata if isinstance(lead.lead_metadata, dict) else (lead.lead_metadata or {})
            }
            lead_responses.append(LeadResponse(**lead_dict))
        
        return {
            "stage": stage,
            "data": lead_responses,
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting leads by stage: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_stage_metrics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get pipeline conversion metrics"""
    
    try:
        broker_id = current_user.get("broker_id")
        metrics = await PipelineService.get_stage_metrics(db=db, broker_id=broker_id)
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting stage metrics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stages/{stage}/inactive")
async def get_inactive_leads_in_stage(
    stage: str,
    inactivity_days: int = Query(7, ge=1),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get leads that have been inactive in a stage for too long"""
    
    try:
        broker_id = current_user.get("broker_id")
        leads = await PipelineService.get_leads_inactive_in_stage(
            db=db,
            stage=stage,
            inactivity_days=inactivity_days,
            broker_id=broker_id
        )
        
        from app.schemas.lead import LeadResponse
        
        # Convert leads to dict format, ensuring metadata is a dict
        lead_responses = []
        for lead in leads:
            lead_dict = {
                "id": lead.id,
                "phone": lead.phone,
                "name": lead.name,
                "email": lead.email,
                "tags": lead.tags or [],
                "status": lead.status,
                "lead_score": lead.lead_score or 0.0,
                "last_contacted": lead.last_contacted,
                "created_at": lead.created_at,
                "updated_at": lead.updated_at,
                "metadata": lead.lead_metadata if isinstance(lead.lead_metadata, dict) else (lead.lead_metadata or {})
            }
            lead_responses.append(LeadResponse(**lead_dict))
        
        return {
            "stage": stage,
            "inactivity_days": inactivity_days,
            "count": len(leads),
            "leads": lead_responses
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting inactive leads: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


