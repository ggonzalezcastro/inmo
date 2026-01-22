"""
Campaign routes for managing marketing campaigns
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc, func
from typing import Optional, List
from pydantic import BaseModel
from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.campaign_service import CampaignService
from app.models.campaign import CampaignStatus, CampaignChannel, CampaignTrigger
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignStepCreate,
    CampaignStepResponse,
    CampaignListResponse,
    CampaignStatsResponse
)
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    campaign_data: CampaignCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new campaign"""
    
    try:
        broker_id = current_user.get("broker_id")  # Get broker_id from current user
        
        campaign = await CampaignService.create_campaign(
            db=db,
            name=campaign_data.name,
            channel=CampaignChannel(campaign_data.channel),
            broker_id=broker_id,
            description=campaign_data.description,
            triggered_by=CampaignTrigger(campaign_data.triggered_by) if campaign_data.triggered_by else CampaignTrigger.MANUAL,
            trigger_condition=campaign_data.trigger_condition,
            max_contacts=campaign_data.max_contacts
        )
        
        return CampaignResponse.model_validate(campaign)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating campaign: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    status: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List campaigns with filters"""
    
    try:
        broker_id = current_user.get("broker_id")
        
        status_enum = None
        if status:
            try:
                status_enum = CampaignStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
        channel_enum = None
        if channel:
            try:
                channel_enum = CampaignChannel(channel)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid channel: {channel}")
        
        campaigns, total = await CampaignService.list_campaigns(
            db=db,
            broker_id=broker_id,
            status=status_enum,
            channel=channel_enum,
            skip=skip,
            limit=limit
        )
        
        return CampaignListResponse(
            data=[CampaignResponse.model_validate(c) for c in campaigns],
            total=total,
            skip=skip,
            limit=limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing campaigns: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get campaign details with steps"""
    
    try:
        broker_id = current_user.get("broker_id")
        
        campaign = await CampaignService.get_campaign(
            db=db,
            campaign_id=campaign_id,
            broker_id=broker_id
        )
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        return CampaignResponse.model_validate(campaign)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    campaign_update: CampaignUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a campaign"""
    
    try:
        broker_id = current_user.get("broker_id")
        
        # Get campaign
        campaign = await CampaignService.get_campaign(
            db=db,
            campaign_id=campaign_id,
            broker_id=broker_id
        )
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Update fields
        update_data = campaign_update.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field == "status" and value:
                campaign.status = CampaignStatus(value)
            elif field == "channel" and value:
                campaign.channel = CampaignChannel(value)
            elif field == "triggered_by" and value:
                campaign.triggered_by = CampaignTrigger(value)
            else:
                if hasattr(campaign, field):
                    setattr(campaign, field, value)
        
        await db.commit()
        await db.refresh(campaign)
        
        return CampaignResponse.model_validate(campaign)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating campaign: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a campaign"""
    
    try:
        broker_id = current_user.get("broker_id")
        
        await CampaignService.delete_campaign(
            db=db,
            campaign_id=campaign_id,
            broker_id=broker_id
        )
        
        return None
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting campaign: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{campaign_id}/steps", response_model=CampaignStepResponse, status_code=201)
async def add_campaign_step(
    campaign_id: int,
    step_data: CampaignStepCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a step to a campaign"""
    
    try:
        broker_id = current_user.get("broker_id")
        
        # Verify campaign exists and belongs to broker
        campaign = await CampaignService.get_campaign(
            db=db,
            campaign_id=campaign_id,
            broker_id=broker_id
        )
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        step = await CampaignService.add_step(
            db=db,
            campaign_id=campaign_id,
            step_number=step_data.step_number,
            action=step_data.action,
            delay_hours=step_data.delay_hours or 0,
            message_template_id=step_data.message_template_id,
            conditions=step_data.conditions,
            target_stage=step_data.target_stage
        )
        
        return CampaignStepResponse.model_validate(step)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding campaign step: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{campaign_id}/steps/{step_id}", status_code=204)
async def delete_campaign_step(
    campaign_id: int,
    step_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a step from a campaign"""
    
    try:
        broker_id = current_user.get("broker_id")
        
        # Verify campaign exists
        campaign = await CampaignService.get_campaign(
            db=db,
            campaign_id=campaign_id,
            broker_id=broker_id
        )
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Delete step
        from app.models.campaign import CampaignStep
        from sqlalchemy.future import select
        
        step_result = await db.execute(
            select(CampaignStep).where(and_(
                CampaignStep.id == step_id,
                CampaignStep.campaign_id == campaign_id
            ))
        )
        step = step_result.scalars().first()
        
        if not step:
            raise HTTPException(status_code=404, detail="Campaign step not found")
        
        await db.delete(step)
        await db.commit()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting campaign step: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{campaign_id}/apply-to-lead/{lead_id}", status_code=201)
async def apply_campaign_to_lead(
    campaign_id: int,
    lead_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually apply a campaign to a lead"""
    
    try:
        broker_id = current_user.get("broker_id")
        
        # Verify campaign exists
        campaign = await CampaignService.get_campaign(
            db=db,
            campaign_id=campaign_id,
            broker_id=broker_id
        )
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        logs = await CampaignService.apply_campaign_to_lead(
            db=db,
            campaign_id=campaign_id,
            lead_id=lead_id
        )
        
        from app.schemas.campaign import CampaignLogResponse
        
        return {
            "message": "Campaign applied successfully",
            "steps_enqueued": len(logs),
            "logs": [CampaignLogResponse.model_validate(log) for log in logs]
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error applying campaign: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/stats", response_model=CampaignStatsResponse)
async def get_campaign_stats(
    campaign_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get campaign statistics"""
    
    try:
        broker_id = current_user.get("broker_id")
        
        stats = await CampaignService.get_campaign_stats(
            db=db,
            campaign_id=campaign_id,
            broker_id=broker_id
        )
        
        return CampaignStatsResponse(**stats)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting campaign stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/logs")
async def get_campaign_logs(
    campaign_id: int,
    lead_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get campaign execution logs"""
    
    try:
        broker_id = current_user.get("broker_id")
        
        # Verify campaign exists
        campaign = await CampaignService.get_campaign(
            db=db,
            campaign_id=campaign_id,
            broker_id=broker_id
        )
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        from app.models.campaign import CampaignLog
        from sqlalchemy.future import select
        from sqlalchemy import and_
        
        query = select(CampaignLog).where(CampaignLog.campaign_id == campaign_id)
        
        if lead_id:
            query = query.where(CampaignLog.lead_id == lead_id)
        
        # Get total count
        count_query = select(func.count(CampaignLog.id)).where(CampaignLog.campaign_id == campaign_id)
        if lead_id:
            count_query = count_query.where(CampaignLog.lead_id == lead_id)
        
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination
        query = query.order_by(desc(CampaignLog.created_at)).offset(skip).limit(limit)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        from app.schemas.campaign import CampaignLogResponse
        
        return {
            "data": [CampaignLogResponse.model_validate(log) for log in logs],
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign logs: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

