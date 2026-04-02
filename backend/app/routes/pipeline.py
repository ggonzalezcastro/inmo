"""
Pipeline routes for managing lead pipeline stages
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.pipeline import PipelineService
from app.services.shared import ActivityService
from pydantic import BaseModel
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class StageChangeRequest(BaseModel):
    new_stage: str
    reason: Optional[str] = None
    close_reason: Optional[str] = None
    close_reason_detail: Optional[str] = None


class AssignAgentRequest(BaseModel):
    agent_id: Optional[int] = None


@router.post("/leads/{lead_id}/move-stage")
async def move_lead_to_stage(
    lead_id: int,
    request: StageChangeRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Move a lead to a new pipeline stage"""
    
    try:
        from sqlalchemy.future import select as sa_select
        from app.models.lead import Lead
        import pytz

        # Fetch old stage before moving
        result = await db.execute(sa_select(Lead).where(Lead.id == lead_id))
        existing_lead = result.scalars().first()
        if not existing_lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        old_stage = existing_lead.pipeline_stage

        lead = await PipelineService.move_lead_to_stage(
            db=db,
            lead_id=lead_id,
            new_stage=request.new_stage,
            reason=request.reason
        )

        # Save close reason when moving to ganado/perdido
        if request.new_stage in ("ganado", "perdido"):
            lead.close_reason = request.close_reason
            lead.close_reason_detail = request.close_reason_detail
            lead.closed_at = datetime.now(pytz.UTC)
            lead.closed_from_stage = old_stage
            await db.commit()
            await db.refresh(lead)
        elif old_stage in ("ganado", "perdido") and request.new_stage not in ("ganado", "perdido"):
            # Reactivating — clear close fields
            lead.close_reason = None
            lead.close_reason_detail = None
            lead.closed_at = None
            lead.closed_from_stage = None
            await db.commit()
            await db.refresh(lead)

        return {
            "message": "Lead stage updated successfully",
            "lead_id": lead.id,
            "old_stage": old_stage,
            "new_stage": lead.pipeline_stage,
            "stage_entered_at": lead.stage_entered_at.isoformat() if lead.stage_entered_at else None
        }

    except HTTPException:
        raise
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


@router.post("/leads/{lead_id}/assign")
async def assign_lead_agent(
    lead_id: int,
    request: AssignAgentRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Assign or unassign an agent to a lead"""
    try:
        from sqlalchemy.future import select as sa_select
        from app.models.lead import Lead
        from app.models.user import User

        result = await db.execute(sa_select(Lead).where(Lead.id == lead_id))
        lead = result.scalars().first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        old_agent_id = lead.assigned_to
        lead.assigned_to = request.agent_id
        await db.commit()

        agent_name = None
        if request.agent_id:
            agent_result = await db.execute(sa_select(User).where(User.id == request.agent_id))
            agent = agent_result.scalars().first()
            if agent:
                agent_name = agent.name

        await ActivityService.log_activity(
            db,
            lead_id=lead_id,
            action_type="agent_assigned",
            details={
                "old_agent_id": old_agent_id,
                "new_agent_id": request.agent_id,
                "agent_name": agent_name,
                "assigned_by": current_user.get("user_id"),
            },
        )

        try:
            from app.core.websocket_manager import ws_manager
            if lead.broker_id:
                await ws_manager.broadcast(lead.broker_id, "lead_assigned", {
                    "lead_id": lead_id,
                    "agent_id": request.agent_id,
                    "agent_name": agent_name,
                })
        except Exception as ws_exc:
            logger.debug("[WS] lead_assigned broadcast error: %s", ws_exc)

        return {"message": "Agent assigned", "lead_id": lead_id, "agent_id": request.agent_id, "agent_name": agent_name}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning agent: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def list_pipeline_agents(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List agents available to assign leads (accessible to all authenticated users)"""
    from sqlalchemy.future import select as sa_select
    from app.models.user import User, UserRole

    broker_id = current_user.get("broker_id")
    if not broker_id:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")

    result = await db.execute(
        sa_select(User).where(
            User.broker_id == broker_id,
            User.role.in_([UserRole.AGENT, UserRole.ADMIN]),
            User.is_active == True,
        ).order_by(User.name)
    )
    agents = result.scalars().all()

    return [{"id": a.id, "name": a.name, "email": a.email} for a in agents]


@router.get("/stages/{stage}/leads")
async def get_leads_by_stage(
    stage: str,
    treatment_type: Optional[str] = Query(None),
    assignedTo: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    created_from: Optional[str] = Query(None),
    created_to: Optional[str] = Query(None),
    calificacion: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get leads in a specific pipeline stage"""
    from datetime import date as date_type

    try:
        broker_id = current_user.get("broker_id")
        current_user_id = current_user.get("user_id") or current_user.get("id")
        if current_user_id:
            try:
                current_user_id = int(current_user_id)
            except (TypeError, ValueError):
                pass

        # Parse date strings to date objects
        parsed_from = date_type.fromisoformat(created_from) if created_from else None
        parsed_to = date_type.fromisoformat(created_to) if created_to else None

        leads, total = await PipelineService.get_leads_by_stage(
            db=db,
            stage=stage,
            broker_id=broker_id,
            treatment_type=treatment_type,
            assigned_to=assignedTo,
            search=search,
            created_from=parsed_from,
            created_to=parsed_to,
            calificacion=calificacion,
            skip=skip,
            limit=limit
        )
        
        from app.schemas.lead import LeadResponse
        from app.models.appointment import Appointment, AppointmentStatus

        # Batch-fetch next upcoming appointment for all leads (for agendado stage badge)
        lead_ids = [lead.id for lead in leads]
        appointments_by_lead: dict = {}
        if lead_ids:
            now = datetime.utcnow()
            apt_result = await db.execute(
                select(Appointment).where(
                    and_(
                        Appointment.lead_id.in_(lead_ids),
                        Appointment.status.in_([
                            AppointmentStatus.SCHEDULED,
                            AppointmentStatus.CONFIRMED,
                        ]),
                        Appointment.start_time >= now,
                    )
                ).order_by(Appointment.start_time)
            )
            for apt in apt_result.scalars().all():
                if apt.lead_id not in appointments_by_lead:
                    appointments_by_lead[apt.lead_id] = apt

        # Convert leads to dict format, ensuring metadata is a dict
        lead_responses = []
        for lead in leads:
            meta = lead.lead_metadata if isinstance(lead.lead_metadata, dict) else (lead.lead_metadata or {})
            # Hide leads exclusively taken by another specific human agent
            human_assigned_to = meta.get("human_assigned_to")
            if meta.get("human_mode") and human_assigned_to and human_assigned_to != current_user_id:
                continue
            # Try to get assigned agent name from relationship (loaded eagerly if available)
            assigned_agent_name = None
            if hasattr(lead, 'assigned_agent') and lead.assigned_agent:
                assigned_agent_name = lead.assigned_agent.name

            next_apt = appointments_by_lead.get(lead.id)
            next_appointment = None
            if next_apt:
                next_appointment = {
                    "id": next_apt.id,
                    "start_time": next_apt.start_time.isoformat(),
                    "status": next_apt.status.value,
                    "meet_url": next_apt.meet_url,
                    "appointment_type": next_apt.appointment_type.value if next_apt.appointment_type else None,
                }

            lead_dict = {
                "id": lead.id,
                "phone": lead.phone,
                "name": lead.name,
                "email": lead.email,
                "tags": lead.tags or [],
                "status": lead.status,
                "lead_score": lead.lead_score or 0.0,
                "pipeline_stage": lead.pipeline_stage,
                "last_contacted": lead.last_contacted,
                "created_at": lead.created_at,
                "updated_at": lead.updated_at,
                "metadata": meta,
                "assigned_to": lead.assigned_to,
                "assigned_agent_name": assigned_agent_name,
                "next_appointment": next_appointment,
            }
            lead_responses.append(lead_dict)
        
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


@router.get("/funnel-metrics")
async def get_funnel_metrics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get conversion funnel metrics: stage counts, conversion rates, avg days, lost by stage"""
    try:
        from app.services.pipeline.metrics_service import get_funnel_metrics
        broker_id = current_user.get("broker_id")
        metrics = await get_funnel_metrics(db=db, broker_id=broker_id)
        return metrics
    except Exception as e:
        logger.error(f"Error getting funnel metrics: {str(e)}", exc_info=True)
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
                "pipeline_stage": lead.pipeline_stage,
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


