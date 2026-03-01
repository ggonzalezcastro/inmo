"""
Campaign execution tasks for Celery
"""
from celery import shared_task
from app.tasks.base import DLQTask
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
from typing import List
import logging
from app.config import settings
from app.models.campaign import (
    Campaign,
    CampaignStep,
    CampaignLog,
    CampaignStatus,
    CampaignTrigger,
    CampaignLogStatus
)
from app.models.lead import Lead
from app.models.template import MessageTemplate
from app.services.shared import TemplateService, TelegramService
from app.services.pipeline import PipelineService
from app.services.campaigns import CampaignService

logger = logging.getLogger(__name__)

# Create async engine for tasks
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(
    name="app.tasks.campaign_executor.execute_campaign_for_lead",
    base=DLQTask,
    bind=True,
    max_retries=5,
    default_retry_delay=120,
)
def execute_campaign_for_lead(self, campaign_id: int, lead_id: int):
    """
    Execute all steps of a campaign for a lead
    
    This task runs asynchronously and processes each step sequentially
    with delays as configured.
    """
    import asyncio
    
    async def _execute():
        # Get database session
        async with AsyncSessionLocal() as db:
            try:
                # Get campaign with steps
                campaign_result = await db.execute(
                    select(Campaign).where(Campaign.id == campaign_id)
                )
                campaign = campaign_result.scalars().first()
                
                if not campaign:
                    logger.error(f"Campaign {campaign_id} not found")
                    return
                
                # Get lead
                lead_result = await db.execute(
                    select(Lead).where(Lead.id == lead_id)
                )
                lead = lead_result.scalars().first()
                
                if not lead:
                    logger.error(f"Lead {lead_id} not found")
                    return
                
                # Get all steps ordered
                steps_result = await db.execute(
                    select(CampaignStep)
                    .where(CampaignStep.campaign_id == campaign_id)
                    .order_by(CampaignStep.step_number)
                )
                steps = steps_result.scalars().all()
                
                if not steps:
                    logger.warning(f"Campaign {campaign_id} has no steps")
                    return
                
                # Execute each step
                for step in steps:
                    # Wait for delay if configured
                    if step.delay_hours > 0:
                        logger.info(f"Waiting {step.delay_hours} hours before step {step.step_number}")
                        # Note: In production, use scheduled tasks for delays
                        # For now, we'll log it and continue immediately
                        # Real implementation would schedule the step execution
                    
                    # Get log entry for this step
                    log_result = await db.execute(
                        select(CampaignLog).where(and_(
                            CampaignLog.campaign_id == campaign_id,
                            CampaignLog.lead_id == lead_id,
                            CampaignLog.step_number == step.step_number
                        ))
                    )
                    log = log_result.scalars().first()
                    
                    if not log:
                        logger.warning(f"Log entry not found for step {step.step_number}")
                        continue
                    
                    if log.status != CampaignLogStatus.PENDING:
                        logger.info(f"Step {step.step_number} already executed (status: {log.status})")
                        continue
                    
                    # Execute step based on action
                    try:
                        if step.action == "send_message":
                            await _execute_send_message(db, campaign, step, lead, log)
                        
                        elif step.action == "make_call":
                            await _execute_make_call(db, campaign, step, lead, log)
                        
                        elif step.action == "schedule_meeting":
                            await _execute_schedule_meeting(db, campaign, step, lead, log)
                        
                        elif step.action == "update_stage":
                            await _execute_update_stage(db, campaign, step, lead, log)
                        
                        else:
                            logger.warning(f"Unknown action: {step.action}")
                            log.status = CampaignLogStatus.FAILED
                            log.response = {"error": f"Unknown action: {step.action}"}
                    
                    except Exception as e:
                        logger.error(f"Error executing step {step.step_number}: {str(e)}", exc_info=True)
                        log.status = CampaignLogStatus.FAILED
                        log.response = {"error": str(e)}
                    
                    log.executed_at = datetime.now()
                    await db.commit()
                    
                    # Move lead to target stage if configured
                    if step.target_stage:
                        try:
                            await PipelineService.move_lead_to_stage(
                                db=db,
                                lead_id=lead_id,
                                new_stage=step.target_stage,
                                reason=f"Campaign {campaign_id} step {step.step_number} completed",
                                triggered_by_campaign=campaign_id
                            )
                        except Exception as e:
                            logger.error(f"Error moving lead to stage: {str(e)}")
            
            except Exception as e:
                logger.error(f"Error in execute_campaign_for_lead: {str(e)}", exc_info=True)
                raise
    
    asyncio.run(_execute())


async def _execute_send_message(db: AsyncSession, campaign, step, lead, log):
    """Execute send_message action"""
    
    if not step.message_template_id:
        raise ValueError("Message template ID required for send_message action")
    
    # Get template
    template_result = await db.execute(
        select(MessageTemplate).where(MessageTemplate.id == step.message_template_id)
    )
    template = template_result.scalars().first()
    
    if not template:
        raise ValueError(f"Template {step.message_template_id} not found")
    
    # Prepare lead data
    lead_data = {
        "id": lead.id,
        "name": lead.name,
        "phone": lead.phone,
        "email": lead.email,
        "lead_score": lead.lead_score,
        "pipeline_stage": lead.pipeline_stage,
        "lead_metadata": lead.lead_metadata or {}
    }
    
    # Render template
    message_text = await TemplateService.render_template(template, lead_data)
    
    # Send message based on channel
    if campaign.channel == "telegram":
        telegram_service = TelegramService()
        # Note: Requires telegram_user_id from lead metadata
        telegram_user_id = lead.lead_metadata.get("telegram_user_id") if lead.lead_metadata else None
        
        if telegram_user_id:
            result = await telegram_service.send_message(
                chat_id=telegram_user_id,
                text=message_text
            )
            log.status = CampaignLogStatus.SENT
            log.response = {"telegram_result": result}
        else:
            raise ValueError("Lead has no telegram_user_id")
    
    else:
        # Other channels not implemented yet
        log.status = CampaignLogStatus.FAILED
        log.response = {"error": f"Channel {campaign.channel} not yet implemented"}


async def _execute_make_call(db: AsyncSession, campaign, step, lead, log):
    """Execute make_call action via VoiceCallService."""
    from app.services.voice import VoiceCallService

    agent_type = (step.config or {}).get("agent_type") or "default"
    try:
        voice_call = await VoiceCallService.initiate_call(
            db=db,
            lead_id=lead.id,
            campaign_id=campaign.id,
            broker_id=campaign.broker_id,
            agent_type=agent_type,
        )
        log.status = CampaignLogStatus.COMPLETED
        log.response = {
            "voice_call_id": voice_call.id,
            "external_call_id": voice_call.external_call_id,
            "status": voice_call.status.value,
        }
    except ValueError as e:
        logger.error("make_call failed for lead=%s campaign=%s: %s", lead.id, campaign.id, str(e))
        log.status = CampaignLogStatus.FAILED
        log.response = {"error": str(e)}


async def _execute_schedule_meeting(db: AsyncSession, campaign, step, lead, log):
    """Execute schedule_meeting action"""
    
    # This will be implemented when appointment service integration is ready
    log.status = CampaignLogStatus.FAILED
    log.response = {"error": "schedule_meeting action not yet implemented"}
    logger.warning("schedule_meeting action not yet implemented")


async def _execute_update_stage(db: AsyncSession, campaign, step, lead, log):
    """Execute update_stage action"""
    
    if not step.target_stage:
        raise ValueError("target_stage required for update_stage action")
    
    await PipelineService.move_lead_to_stage(
        db=db,
        lead_id=lead.id,
        new_stage=step.target_stage,
        reason=f"Campaign {campaign.id} step {step.step_number}",
        triggered_by_campaign=campaign.id
    )
    
    log.status = CampaignLogStatus.SENT
    log.response = {"stage": step.target_stage}


def _build_eligible_leads_query(campaign: Campaign):
    """
    Build SQL query for leads eligible for this campaign's trigger (no N+1).
    Returns select(Lead).where(...) with broker_id and trigger conditions.
    """
    condition = campaign.trigger_condition or {}
    base = select(Lead).where(Lead.broker_id == campaign.broker_id)
    
    if campaign.triggered_by == CampaignTrigger.LEAD_SCORE:
        score_min = condition.get("score_min")
        score_max = condition.get("score_max")
        if score_min is not None:
            base = base.where(Lead.lead_score >= score_min)
        if score_max is not None:
            base = base.where(Lead.lead_score <= score_max)
        return base
    
    if campaign.triggered_by == CampaignTrigger.STAGE_CHANGE:
        target_stage = condition.get("stage")
        if target_stage:
            return base.where(Lead.pipeline_stage == target_stage)
        return base.where(Lead.id == -1)  # no stage = no leads
    
    if campaign.triggered_by == CampaignTrigger.INACTIVITY:
        inactivity_days = condition.get("inactivity_days", 30)
        cutoff = datetime.now() - timedelta(days=inactivity_days)
        return base.where(
            or_(
                Lead.last_contacted < cutoff,
                and_(
                    Lead.last_contacted.is_(None),
                    Lead.created_at < cutoff
                )
            )
        )
    
    return base.where(Lead.id == -1)  # MANUAL or unknown


@shared_task(name="app.tasks.campaign_executor.check_trigger_campaigns")
def check_trigger_campaigns():
    """
    Run every hour: check all active campaigns, apply to matching leads.
    Uses one query per campaign to get eligible leads (avoids N+1).
    """
    import asyncio
    
    async def _check():
        async with AsyncSessionLocal() as db:
            try:
                campaigns_result = await db.execute(
                    select(Campaign).where(Campaign.status == CampaignStatus.ACTIVE)
                )
                campaigns = campaigns_result.scalars().all()
                
                logger.info(f"Checking {len(campaigns)} active campaigns for triggers")
                
                for campaign in campaigns:
                    if campaign.triggered_by == CampaignTrigger.MANUAL:
                        continue
                    
                    try:
                        query = _build_eligible_leads_query(campaign)
                        leads_result = await db.execute(query)
                        eligible_leads = leads_result.scalars().all()
                        
                        if campaign.max_contacts:
                            stats = await CampaignService.get_campaign_stats(
                                db=db,
                                campaign_id=campaign.id
                            )
                            if stats["unique_leads"] >= campaign.max_contacts:
                                logger.info(f"Campaign {campaign.id} reached max_contacts limit")
                                continue
                        
                        applied_count = 0
                        for lead in eligible_leads:
                            campaign_history = lead.campaign_history or []
                            if not isinstance(campaign_history, list):
                                campaign_history = []
                            already_applied = any(
                                log.get("campaign_id") == campaign.id for log in campaign_history
                            )
                            if already_applied:
                                continue
                            if campaign.max_contacts and applied_count >= campaign.max_contacts:
                                break
                            
                            logs = await CampaignService.apply_campaign_to_lead(
                                db=db,
                                campaign_id=campaign.id,
                                lead_id=lead.id
                            )
                            campaign_history.append({
                                "campaign_id": campaign.id,
                                "applied_at": datetime.now().isoformat(),
                                "trigger": campaign.triggered_by.value,
                                "steps_enqueued": len(logs)
                            })
                            lead.campaign_history = campaign_history
                            applied_count += 1
                            await db.commit()
                            execute_campaign_for_lead.delay(campaign.id, lead.id)
                            logger.info(f"Campaign {campaign.id} applied to lead {lead.id}")
                    
                    except Exception as e:
                        logger.error(f"Error checking campaign {campaign.id}: {str(e)}", exc_info=True)
                        try:
                            await db.rollback()
                        except Exception:
                            pass
                        continue
            
            except Exception as e:
                logger.error(f"Error in check_trigger_campaigns: {str(e)}", exc_info=True)
                raise
    
    asyncio.run(_check())


# Import MessageTemplate
from app.models.template import MessageTemplate

