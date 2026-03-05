"""
Campaign routes for managing marketing campaigns
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, desc, func
from sqlalchemy.exc import IntegrityError, DBAPIError
from typing import Optional, List
from pydantic import BaseModel
from app.database import get_db
from app.middleware.auth import get_current_user
from app.services.campaigns import CampaignService
from app.models.campaign import Campaign, CampaignStatus, CampaignChannel, CampaignTrigger
from app.models.campaign import CampaignStep
from sqlalchemy.orm.attributes import set_committed_value
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignStepCreate,
    CampaignStepUpdate,
    CampaignStepResponse,
    CampaignListResponse,
    CampaignStatsResponse
)
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


def _handle_db_error(e: Exception, action: str = "operación") -> HTTPException:
    """Convert raw DB/asyncpg errors into clean HTTP responses."""
    msg = str(e)
    # Invalid enum value (asyncpg)
    if "invalid input value for enum" in msg or "InvalidTextRepresentationError" in msg:
        import re
        m = re.search(r'invalid input value for enum \w+: "(\w+)"', msg)
        val = m.group(1) if m else "valor desconocido"
        return HTTPException(status_code=422, detail=f"Valor inválido: '{val}'. Revisa los campos de selección.")
    # Unique constraint
    if "unique" in msg.lower() or "duplicate" in msg.lower():
        return HTTPException(status_code=409, detail="Ya existe un registro con esos datos.")
    # Foreign key
    if "foreign key" in msg.lower():
        return HTTPException(status_code=422, detail="Referencia inválida: uno de los IDs no existe.")
    # Generic DB
    logger.error(f"DB error during {action}: {msg}", exc_info=True)
    return HTTPException(status_code=500, detail=f"Error de base de datos al {action}.")


async def _refresh_campaign_with_steps(db: AsyncSession, campaign: Campaign) -> Campaign:
    """Reload steps after commit without triggering lazy-load on the collection."""
    await db.refresh(campaign)
    steps_result = await db.execute(
        select(CampaignStep)
        .where(CampaignStep.campaign_id == campaign.id)
        .order_by(CampaignStep.step_number)
    )
    # Use set_committed_value to inject directly — avoids async lazy-load on collection replace
    set_committed_value(campaign, 'steps', list(steps_result.scalars().all()))
    return campaign


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    campaign_data: CampaignCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new campaign"""
    
    try:
        broker_id = current_user.get("broker_id")
        
        campaign = await CampaignService.create_campaign(
            db=db,
            name=campaign_data.name,
            channel=CampaignChannel(campaign_data.channel),
            broker_id=broker_id,
            description=campaign_data.description,
            triggered_by=CampaignTrigger(campaign_data.triggered_by) if campaign_data.triggered_by else CampaignTrigger.MANUAL,
            trigger_condition=campaign_data.trigger_condition,
            max_contacts=campaign_data.max_contacts,
            created_by=current_user.get("id")
        )
        
        await _refresh_campaign_with_steps(db, campaign)
        return CampaignResponse.model_validate(campaign)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (IntegrityError, DBAPIError) as e:
        raise _handle_db_error(e, "crear la campaña")
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_db_error(e, "crear la campaña")


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
    except (IntegrityError, DBAPIError) as e:
        raise _handle_db_error(e, "listar campañas")
    except Exception as e:
        raise _handle_db_error(e, "listar campañas")


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
    except (IntegrityError, DBAPIError) as e:
        raise _handle_db_error(e, "obtener la campaña")
    except Exception as e:
        raise _handle_db_error(e, "obtener la campaña")


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
        await _refresh_campaign_with_steps(db, campaign)
        
        return CampaignResponse.model_validate(campaign)
    except Exception as e:
        raise _handle_db_error(e, "actualizar la campaña")


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
    except (IntegrityError, DBAPIError) as e:
        raise _handle_db_error(e, "eliminar la campaña")
    except Exception as e:
        raise _handle_db_error(e, "eliminar la campaña")


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
            message_text=step_data.message_text,
            use_ai_message=step_data.use_ai_message,
            step_channel=step_data.channel.value if step_data.channel else None,
            conditions=step_data.conditions,
            target_stage=step_data.target_stage
        )
        
        return CampaignStepResponse.model_validate(step)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (IntegrityError, DBAPIError) as e:
        raise _handle_db_error(e, "agregar paso de campaña")
    except Exception as e:
        raise _handle_db_error(e, "agregar paso de campaña")


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
    except (IntegrityError, DBAPIError) as e:
        raise _handle_db_error(e, "eliminar paso de campaña")
    except Exception as e:
        raise _handle_db_error(e, "eliminar paso de campaña")


@router.patch("/{campaign_id}/steps/{step_id}", response_model=CampaignStepResponse)
async def update_campaign_step(
    campaign_id: int,
    step_id: int,
    step_data: CampaignStepUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a step in a campaign"""
    try:
        broker_id = current_user.get("broker_id")
        campaign = await CampaignService.get_campaign(db=db, campaign_id=campaign_id, broker_id=broker_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        from app.models.campaign import CampaignStep as CampaignStepModel
        from sqlalchemy.future import select as sa_select

        result = await db.execute(
            sa_select(CampaignStepModel).where(and_(
                CampaignStepModel.id == step_id,
                CampaignStepModel.campaign_id == campaign_id
            ))
        )
        step = result.scalars().first()
        if not step:
            raise HTTPException(status_code=404, detail="Step not found")

        update_data = step_data.model_dump(exclude_unset=True)
        if 'channel' in update_data and update_data['channel'] is not None:
            update_data['channel'] = update_data['channel'].value
        for field, value in update_data.items():
            setattr(step, field, value)

        await db.commit()
        await db.refresh(step)
        return CampaignStepResponse.model_validate(step)

    except HTTPException:
        raise
    except (IntegrityError, DBAPIError) as e:
        raise _handle_db_error(e, "actualizar paso de campaña")
    except Exception as e:
        raise _handle_db_error(e, "actualizar paso de campaña")


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


@router.get("/{campaign_id}/matching-leads")
async def get_matching_leads(
    campaign_id: int,
    limit: int = Query(5, ge=1, le=20),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Return count + sample of leads that currently match this campaign's trigger."""
    try:
        from app.models.lead import Lead
        from datetime import timedelta, timezone
        from sqlalchemy import case

        broker_id = current_user.get("broker_id")
        campaign = await CampaignService.get_campaign(db=db, campaign_id=campaign_id, broker_id=broker_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        condition = campaign.trigger_condition or {}
        trigger = campaign.triggered_by.value if campaign.triggered_by else "manual"
        base_q = select(Lead).where(Lead.broker_id == broker_id)

        if trigger == "manual":
            # Manual: show total active leads as potential targets
            count_result = await db.execute(select(func.count(Lead.id)).where(Lead.broker_id == broker_id))
            total = count_result.scalar() or 0
            sample_result = await db.execute(base_q.order_by(Lead.created_at.desc()).limit(limit))
            sample = sample_result.scalars().all()
            return {
                "trigger": trigger,
                "total": total,
                "note": "Campaña manual — aplícala a los leads que desees.",
                "leads": [{"id": l.id, "name": l.name or f"Lead #{l.id}"} for l in sample],
            }

        elif trigger == "inactivity":
            days = int(condition.get("inactivity_days", 7))
            cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=days))
            inactive_q = base_q.where(
                (Lead.last_contacted == None) | (Lead.last_contacted < cutoff)
            )
            count_result = await db.execute(select(func.count(Lead.id)).where(
                Lead.broker_id == broker_id,
                (Lead.last_contacted == None) | (Lead.last_contacted < cutoff)
            ))
            total = count_result.scalar() or 0
            sample_result = await db.execute(inactive_q.order_by(Lead.created_at.desc()).limit(limit))
            sample = sample_result.scalars().all()
            return {
                "trigger": trigger,
                "total": total,
                "note": f"{total} lead{'s' if total != 1 else ''} sin contacto hace más de {days} días.",
                "leads": [{"id": l.id, "name": l.name or f"Lead #{l.id}"} for l in sample],
            }

        elif trigger == "lead_score":
            score_min = float(condition.get("score_min", 0))
            score_max = float(condition.get("score_max", 100))
            score_q = base_q.where(Lead.lead_score >= score_min, Lead.lead_score <= score_max)
            count_result = await db.execute(select(func.count(Lead.id)).where(
                Lead.broker_id == broker_id,
                Lead.lead_score >= score_min, Lead.lead_score <= score_max
            ))
            total = count_result.scalar() or 0
            sample_result = await db.execute(score_q.order_by(Lead.lead_score.desc()).limit(limit))
            sample = sample_result.scalars().all()
            return {
                "trigger": trigger,
                "total": total,
                "note": f"{total} lead{'s' if total != 1 else ''} con score entre {score_min:.0f} y {score_max:.0f}.",
                "leads": [{"id": l.id, "name": l.name or f"Lead #{l.id}", "score": l.lead_score} for l in sample],
            }

        elif trigger == "stage_change":
            stage = condition.get("stage", "")
            stage_q = base_q.where(Lead.pipeline_stage == stage)
            count_result = await db.execute(select(func.count(Lead.id)).where(
                Lead.broker_id == broker_id, Lead.pipeline_stage == stage
            ))
            total = count_result.scalar() or 0
            sample_result = await db.execute(stage_q.order_by(Lead.created_at.desc()).limit(limit))
            sample = sample_result.scalars().all()
            return {
                "trigger": trigger,
                "total": total,
                "note": f"{total} lead{'s' if total != 1 else ''} actualmente en etapa '{stage}'.",
                "leads": [{"id": l.id, "name": l.name or f"Lead #{l.id}"} for l in sample],
            }

        return {"trigger": trigger, "total": 0, "note": "", "leads": []}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting matching leads: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al obtener leads coincidentes.")


@router.get("/{campaign_id}/stats", response_model=CampaignStatsResponse)
async def get_campaign_stats(
    campaign_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get campaign statistics"""
    try:
        broker_id = current_user.get("broker_id")
        stats = await CampaignService.get_campaign_stats(db=db, campaign_id=campaign_id, broker_id=broker_id)
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


# ── Approval workflow ─────────────────────────────────────────────────────────

@router.post("/{campaign_id}/preview-message")
async def preview_ai_message(
    campaign_id: int,
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate a sample AI message for a campaign step (preview only)."""
    try:
        broker_id = current_user.get("broker_id")
        campaign = await CampaignService.get_campaign(db=db, campaign_id=campaign_id, broker_id=broker_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        from app.services.llm.facade import LLMServiceFacade

        channel = body.get("channel") or campaign.channel.value
        trigger = campaign.triggered_by.value if campaign.triggered_by else "manual"
        action = body.get("action", "send_message")

        trigger_labels = {
            "manual": "aplicado manualmente por el agente",
            "inactivity": "sin contacto por varios días",
            "lead_score": "puntuación alta de calificación",
            "stage_change": "cambio de etapa en el pipeline",
        }
        channel_labels = {
            "telegram": "Telegram", "whatsapp": "WhatsApp",
            "call": "llamada telefónica", "email": "correo",
        }

        prompt = (
            f"Eres Sofía, una asesora inmobiliaria chilena de {campaign.name or 'la empresa'}. "
            f"Genera UN mensaje corto y natural para enviar por {channel_labels.get(channel, channel)} "
            f"a un lead inmobiliario cuyo contexto es: {trigger_labels.get(trigger, trigger)}. "
            f"El objetivo de la campaña es: {campaign.description or campaign.name}. "
            "El mensaje debe ser profesional, cálido y orientado a reconectar o avanzar en el proceso. "
            "Máximo 3 oraciones. Responde SOLO con el texto del mensaje, sin explicaciones."
        )

        text = await LLMServiceFacade.generate_response(prompt)
        return {"message": text.strip()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating preview message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="No se pudo generar el mensaje de vista previa.")

@router.put("/{campaign_id}/submit", response_model=CampaignResponse)
async def submit_campaign_for_review(
    campaign_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Agent submits a DRAFT campaign for admin review → PENDING_REVIEW."""
    try:
        broker_id = current_user.get("broker_id")
        campaign = await CampaignService.get_campaign(db=db, campaign_id=campaign_id, broker_id=broker_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.status.value != "draft":
            raise HTTPException(status_code=400, detail="Solo campañas en DRAFT pueden enviarse a revisión")
        campaign.status = CampaignStatus("pending_review")
        await db.commit()
        await _refresh_campaign_with_steps(db, campaign)
        return CampaignResponse.model_validate(campaign)
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_db_error(e, "enviar campaña a revisión")


@router.put("/{campaign_id}/activate", response_model=CampaignResponse)
async def activate_campaign(
    campaign_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin activates a PENDING_REVIEW campaign → ACTIVE."""
    try:
        user_role = current_user.get("role", "")
        if user_role not in ("ADMIN", "SUPERADMIN"):
            raise HTTPException(status_code=403, detail="Solo admins pueden activar campañas")
        broker_id = current_user.get("broker_id")
        campaign = await CampaignService.get_campaign(db=db, campaign_id=campaign_id, broker_id=broker_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.status.value not in ("pending_review", "paused", "draft"):
            raise HTTPException(status_code=400, detail=f"No se puede activar una campaña en estado '{campaign.status.value}'")
        campaign.status = CampaignStatus("active")
        campaign.approved_by = current_user.get("id")
        await db.commit()
        await _refresh_campaign_with_steps(db, campaign)
        return CampaignResponse.model_validate(campaign)
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_db_error(e, "activar campaña")


@router.put("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Admin pauses an ACTIVE campaign → PAUSED."""
    try:
        user_role = current_user.get("role", "")
        if user_role not in ("ADMIN", "SUPERADMIN"):
            raise HTTPException(status_code=403, detail="Solo admins pueden pausar campañas")
        broker_id = current_user.get("broker_id")
        campaign = await CampaignService.get_campaign(db=db, campaign_id=campaign_id, broker_id=broker_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.status.value != "active":
            raise HTTPException(status_code=400, detail="Solo campañas activas pueden pausarse")
        campaign.status = CampaignStatus("paused")
        await db.commit()
        await _refresh_campaign_with_steps(db, campaign)
        return CampaignResponse.model_validate(campaign)
    except HTTPException:
        raise
    except Exception as e:
        raise _handle_db_error(e, "pausar campaña")

