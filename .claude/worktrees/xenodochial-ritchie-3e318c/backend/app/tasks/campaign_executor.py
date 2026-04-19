"""
Campaign execution tasks for Celery
"""
from celery import shared_task
from app.tasks.base import DLQTask
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from typing import Optional
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

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── Single-step execution ─────────────────────────────────────────────────────

@shared_task(
    name="app.tasks.campaign_executor.execute_campaign_step",
    base=DLQTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def execute_campaign_step(self, campaign_id: int, lead_id: int, step_number: int):
    """
    Execute one step of a campaign for a lead, then schedule the next step
    with countdown = next_step.delay_hours * 3600.
    """
    import asyncio

    async def _run():
        async with AsyncSessionLocal() as db:
            # Load campaign
            campaign_result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
            campaign = campaign_result.scalars().first()
            if not campaign:
                logger.error("Campaign %s not found", campaign_id)
                return

            # Load lead
            lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = lead_result.scalars().first()
            if not lead:
                logger.error("Lead %s not found", lead_id)
                return

            # Load the specific step
            step_result = await db.execute(
                select(CampaignStep).where(
                    CampaignStep.campaign_id == campaign_id,
                    CampaignStep.step_number == step_number
                )
            )
            step = step_result.scalars().first()
            if not step:
                logger.warning("Step %s not found in campaign %s", step_number, campaign_id)
                return

            # Load or create log for this step
            log_result = await db.execute(
                select(CampaignLog).where(
                    CampaignLog.campaign_id == campaign_id,
                    CampaignLog.lead_id == lead_id,
                    CampaignLog.step_number == step_number
                )
            )
            log = log_result.scalars().first()
            if not log:
                log = CampaignLog(
                    campaign_id=campaign_id,
                    lead_id=lead_id,
                    step_number=step_number,
                    status=CampaignLogStatus.PENDING
                )
                db.add(log)

            if log.status != CampaignLogStatus.PENDING:
                logger.info("Step %s already processed (status=%s)", step_number, log.status)
            else:
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
                        log.status = CampaignLogStatus.FAILED
                        log.response = {"error": f"Unknown action: {step.action}"}
                except Exception as e:
                    logger.error("Error executing step %s: %s", step_number, str(e), exc_info=True)
                    log.status = CampaignLogStatus.FAILED
                    log.response = {"error": str(e)}

                log.executed_at = datetime.now()

            await db.commit()

            # Schedule next step
            next_step_result = await db.execute(
                select(CampaignStep).where(
                    CampaignStep.campaign_id == campaign_id,
                    CampaignStep.step_number == step_number + 1
                )
            )
            next_step = next_step_result.scalars().first()
            if next_step:
                countdown_seconds = next_step.delay_hours * 3600
                execute_campaign_step.apply_async(
                    args=[campaign_id, lead_id, next_step.step_number],
                    countdown=countdown_seconds
                )
                logger.info(
                    "Scheduled step %s for campaign %s lead %s in %s seconds",
                    next_step.step_number, campaign_id, lead_id, countdown_seconds
                )

    asyncio.run(_run())


@shared_task(
    name="app.tasks.campaign_executor.execute_campaign_for_lead",
    base=DLQTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def execute_campaign_for_lead(self, campaign_id: int, lead_id: int):
    """
    Start campaign execution for a lead — schedules step 1 immediately.
    All subsequent steps are chained with their delay_hours.
    """
    import asyncio

    async def _run():
        async with AsyncSessionLocal() as db:
            first_step_result = await db.execute(
                select(CampaignStep)
                .where(CampaignStep.campaign_id == campaign_id)
                .order_by(CampaignStep.step_number)
                .limit(1)
            )
            first_step = first_step_result.scalars().first()
            if not first_step:
                logger.warning("Campaign %s has no steps", campaign_id)
                return

            # Apply delay of first step (normally 0)
            countdown_seconds = first_step.delay_hours * 3600
            execute_campaign_step.apply_async(
                args=[campaign_id, lead_id, first_step.step_number],
                countdown=countdown_seconds
            )

    asyncio.run(_run())


# ── Step action handlers ──────────────────────────────────────────────────────

async def _resolve_message(campaign, step, lead) -> str:
    """Get the message text for a send_message step."""
    # Per-step free text takes priority
    if step.message_text:
        return step.message_text
    # AI-generated message placeholder
    if step.use_ai_message:
        return f"Hola {lead.name or 'estimado/a'}, te contactamos para seguir apoyándote en tu búsqueda de propiedad."
    # Template
    raise ValueError("Step has no message_text, use_ai_message=False, and no template_id")


async def _get_effective_channel(campaign, step) -> str:
    """Resolve which channel to use: step-level override or campaign default."""
    if step.step_channel:
        return step.step_channel.value if hasattr(step.step_channel, 'value') else step.step_channel
    return campaign.channel.value if hasattr(campaign.channel, 'value') else campaign.channel


async def _execute_send_message(db: AsyncSession, campaign, step, lead, log):
    """Execute send_message action."""
    channel = await _get_effective_channel(campaign, step)

    if step.message_template_id:
        template_result = await db.execute(
            select(MessageTemplate).where(MessageTemplate.id == step.message_template_id)
        )
        template = template_result.scalars().first()
        if not template:
            raise ValueError(f"Template {step.message_template_id} not found")
        lead_data = {
            "id": lead.id, "name": lead.name, "phone": lead.phone,
            "email": lead.email, "lead_score": lead.lead_score,
            "pipeline_stage": lead.pipeline_stage,
            "lead_metadata": lead.lead_metadata or {}
        }
        message_text = await TemplateService.render_template(template, lead_data)
    else:
        message_text = await _resolve_message(campaign, step, lead)

    if channel == "telegram":
        telegram_user_id = (lead.lead_metadata or {}).get("telegram_user_id")
        if not telegram_user_id:
            raise ValueError("Lead has no telegram_user_id")
        telegram_service = TelegramService()
        result = await telegram_service.send_message(chat_id=telegram_user_id, text=message_text)
        log.status = CampaignLogStatus.SENT
        log.response = {"channel": "telegram", "result": result}
    elif channel == "whatsapp":
        # WhatsApp integration placeholder
        phone = lead.phone
        if not phone:
            raise ValueError("Lead has no phone for WhatsApp")
        # TODO: integrate WhatsApp service
        log.status = CampaignLogStatus.SENT
        log.response = {"channel": "whatsapp", "phone": phone, "message": message_text}
        logger.info("WhatsApp message queued for lead %s: %s", lead.id, message_text[:60])
    else:
        log.status = CampaignLogStatus.FAILED
        log.response = {"error": f"Channel '{channel}' not yet supported"}


async def _execute_make_call(db: AsyncSession, campaign, step, lead, log):
    """Execute make_call action via VoiceCallService."""
    from app.services.voice import VoiceCallService
    agent_type = (step.conditions or {}).get("agent_type") or "default"
    try:
        voice_call = await VoiceCallService.initiate_call(
            db=db,
            lead_id=lead.id,
            campaign_id=campaign.id,
            broker_id=campaign.broker_id,
            agent_type=agent_type,
        )
        log.status = CampaignLogStatus.SENT
        log.response = {
            "voice_call_id": voice_call.id,
            "external_call_id": voice_call.external_call_id,
        }
    except Exception as e:
        logger.error("make_call failed for lead=%s: %s", lead.id, str(e))
        raise


async def _execute_schedule_meeting(db: AsyncSession, campaign, step, lead, log):
    """Schedule meeting — not yet implemented."""
    log.status = CampaignLogStatus.FAILED
    log.response = {"error": "schedule_meeting not yet implemented"}
    logger.warning("schedule_meeting action not yet implemented")


async def _execute_update_stage(db: AsyncSession, campaign, step, lead, log):
    """Execute update_stage action."""
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


# ── Trigger evaluation ────────────────────────────────────────────────────────

def _build_eligible_leads_query(campaign: Campaign):
    """Build query for leads matching campaign's trigger conditions."""
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
        return base.where(Lead.id == -1)

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
    """Hourly: find ACTIVE campaigns, apply to eligible leads."""
    import asyncio

    async def _check():
        async with AsyncSessionLocal() as db:
            campaigns_result = await db.execute(
                select(Campaign).where(Campaign.status == CampaignStatus.ACTIVE)
            )
            campaigns = campaigns_result.scalars().all()
            logger.info("Checking %s active campaigns", len(campaigns))

            for campaign in campaigns:
                if campaign.triggered_by == CampaignTrigger.MANUAL:
                    continue
                try:
                    query = _build_eligible_leads_query(campaign)
                    leads_result = await db.execute(query)
                    eligible_leads = leads_result.scalars().all()

                    if campaign.max_contacts:
                        stats = await CampaignService.get_campaign_stats(db=db, campaign_id=campaign.id)
                        if stats["unique_leads"] >= campaign.max_contacts:
                            continue

                    applied_count = 0
                    for lead in eligible_leads:
                        campaign_history = lead.campaign_history or []
                        if not isinstance(campaign_history, list):
                            campaign_history = []
                        if any(h.get("campaign_id") == campaign.id for h in campaign_history):
                            continue
                        if campaign.max_contacts and applied_count >= campaign.max_contacts:
                            break

                        logs = await CampaignService.apply_campaign_to_lead(
                            db=db, campaign_id=campaign.id, lead_id=lead.id
                        )
                        campaign_history.append({
                            "campaign_id": campaign.id,
                            "applied_at": datetime.now().isoformat(),
                            "trigger": campaign.triggered_by.value,
                        })
                        lead.campaign_history = campaign_history
                        applied_count += 1
                        await db.commit()
                        execute_campaign_for_lead.delay(campaign.id, lead.id)

                except Exception as e:
                    logger.error("Error checking campaign %s: %s", campaign.id, str(e), exc_info=True)
                    try:
                        await db.rollback()
                    except Exception:
                        pass

    asyncio.run(_check())
