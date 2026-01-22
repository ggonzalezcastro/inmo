"""
Campaign execution tasks for Celery
"""
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import and_
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
from app.services.template_service import TemplateService
from app.services.telegram_service import TelegramService
from app.services.pipeline_service import PipelineService
from app.services.campaign_service import CampaignService

logger = logging.getLogger(__name__)

# Create async engine for tasks
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(name="app.tasks.campaign_executor.execute_campaign_for_lead", bind=True, max_retries=3)
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
    """Execute make_call action"""
    
    # This will be implemented when voice service is ready
    log.status = CampaignLogStatus.FAILED
    log.response = {"error": "make_call action not yet implemented"}
    logger.warning("make_call action not yet implemented")


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


@shared_task(name="app.tasks.campaign_executor.check_trigger_campaigns")
def check_trigger_campaigns():
    """
    Run every hour: check all active campaigns, apply to matching leads
    
    This task checks all active campaigns and applies them to leads
    that match the trigger conditions.
    """
    import asyncio
    
    async def _check():
        # Get database session
        async with AsyncSessionLocal() as db:
            try:
                # Get all active campaigns
                campaigns_result = await db.execute(
                    select(Campaign).where(Campaign.status == CampaignStatus.ACTIVE)
                )
                campaigns = campaigns_result.scalars().all()
                
                logger.info(f"Checking {len(campaigns)} active campaigns for triggers")
                
                for campaign in campaigns:
                    if campaign.triggered_by == CampaignTrigger.MANUAL:
                        continue  # Skip manual campaigns
                    
                    try:
                        # Get all leads (or filter by broker_id if needed)
                        leads_result = await db.execute(select(Lead))
                        leads = leads_result.scalars().all()
                        
                        for lead in leads:
                            # Check trigger conditions
                            from app.services.campaign_service import CampaignService
                            
                            should_trigger = await CampaignService.check_trigger_conditions(
                                db=db,
                                campaign=campaign,
                                lead=lead
                            )
                            
                            if should_trigger:
                                # Check if campaign already applied
                                campaign_history = lead.campaign_history or []
                                already_applied = any(
                                    log.get("campaign_id") == campaign.id 
                                    for log in campaign_history
                                )
                                
                                if not already_applied:
                                    # Check max_contacts limit
                                    if campaign.max_contacts:
                                        stats = await CampaignService.get_campaign_stats(
                                            db=db,
                                            campaign_id=campaign.id
                                        )
                                        if stats["unique_leads"] >= campaign.max_contacts:
                                            logger.info(f"Campaign {campaign.id} reached max_contacts limit")
                                            continue
                                    
                                    # Apply campaign
                                    logs = await CampaignService.apply_campaign_to_lead(
                                        db=db,
                                        campaign_id=campaign.id,
                                        lead_id=lead.id
                                    )
                                    
                                    # Update campaign history
                                    if not isinstance(campaign_history, list):
                                        campaign_history = []
                                    
                                    campaign_history.append({
                                        "campaign_id": campaign.id,
                                        "applied_at": datetime.now().isoformat(),
                                        "trigger": campaign.triggered_by.value,
                                        "steps_enqueued": len(logs)
                                    })
                                    lead.campaign_history = campaign_history
                                    await db.commit()
                                    
                                    # Enqueue execution task
                                    execute_campaign_for_lead.delay(campaign.id, lead.id)
                                    
                                    logger.info(f"Campaign {campaign.id} applied to lead {lead.id}")
                    
                    except Exception as e:
                        logger.error(f"Error checking campaign {campaign.id}: {str(e)}", exc_info=True)
                        continue
            
            except Exception as e:
                logger.error(f"Error in check_trigger_campaigns: {str(e)}", exc_info=True)
                raise
    
    asyncio.run(_check())


# Import MessageTemplate
from app.models.template import MessageTemplate

