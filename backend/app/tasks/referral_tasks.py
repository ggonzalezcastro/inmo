"""Celery tasks for won-lead referral outreach."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select

from app.models.broker_chat_config import BrokerChatConfig
from app.models.campaign import Campaign, CampaignStatus
from app.models.chat_message import ChatMessage, ChatProvider
from app.models.lead import Lead
from app.shared.pipeline_stages import PIPELINE_STAGE_WON
from app.tasks.base import DLQTask

logger = logging.getLogger(__name__)


def enqueue_referral_outreach(lead_id: int, broker_id: int) -> None:
    """Queue outreach after the stage-changing transaction has committed."""
    try:
        start_referral_outreach.delay(lead_id, broker_id)
    except Exception as exc:
        # The stage change itself must remain successful if Redis is temporarily down.
        logger.error(
            "Could not enqueue referral outreach for lead=%s broker=%s: %s",
            lead_id,
            broker_id,
            exc,
            exc_info=True,
        )


async def _delivery_target(db, lead: Lead) -> tuple[str, str] | None:
    latest_result = await db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.lead_id == lead.id,
            ChatMessage.broker_id == lead.broker_id,
            ChatMessage.provider.in_([ChatProvider.WHATSAPP, ChatProvider.TELEGRAM]),
        )
        .order_by(ChatMessage.created_at.desc())
        .limit(1)
    )
    latest = latest_result.scalars().first()
    if latest:
        provider = latest.provider.value if hasattr(latest.provider, "value") else str(latest.provider)
        return provider, latest.channel_user_id

    config_result = await db.execute(
        select(BrokerChatConfig).where(BrokerChatConfig.broker_id == lead.broker_id)
    )
    config = config_result.scalars().first()
    enabled = list(config.enabled_providers or []) if config else []
    if "whatsapp" in enabled and lead.phone:
        return "whatsapp", lead.phone

    telegram_user_id = (lead.lead_metadata or {}).get("telegram_user_id")
    if "telegram" in enabled and telegram_user_id:
        return "telegram", str(telegram_user_id)
    return None


def _default_referral_message(lead: Lead) -> str:
    greeting = f"Hola {lead.name.strip()}," if lead.name and lead.name.strip() else "Hola,"
    return (
        f"{greeting} gracias nuevamente por confiar en nosotros. "
        "Si conoces a alguien que esté buscando una propiedad y te acomoda compartirlo, "
        "puedes enviarme su nombre y teléfono. Sin compromiso 😊"
    )


@shared_task(
    name="app.tasks.referral_tasks.start_referral_outreach",
    base=DLQTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def start_referral_outreach(self, lead_id: int, broker_id: int) -> None:
    """Choose exactly one route: active referral campaign or gentle fallback."""
    import asyncio

    async def _run() -> None:
        # Reuse the campaign worker's engine/session configuration.
        from app.tasks.campaign_executor import AsyncSessionLocal, execute_campaign_for_lead

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Lead).where(
                    Lead.id == lead_id,
                    Lead.broker_id == broker_id,
                )
            )
            lead = result.scalars().first()
            if not lead or lead.pipeline_stage != PIPELINE_STAGE_WON:
                return

            metadata = dict(lead.lead_metadata or {})
            if metadata.get("referral_status") in {"collected", "declined"}:
                return
            if metadata.get("referral_outreach_status") in {
                "sending", "asked", "campaign_active", "collected", "declined"
            }:
                return

            # Claim before any external send. A second queued task will stop here.
            metadata.update({
                "referral_outreach_status": "sending",
                "referral_outreach_started_at": datetime.now(timezone.utc).isoformat(),
                "current_agent": "referral",
            })
            lead.lead_metadata = metadata
            await db.commit()

            campaign_result = await db.execute(
                select(Campaign)
                .where(
                    Campaign.broker_id == broker_id,
                    Campaign.status == CampaignStatus.ACTIVE,
                    Campaign.is_referral_campaign == True,
                )
                .order_by(Campaign.id.asc())
                .limit(1)
            )
            campaign = campaign_result.scalars().first()

            if campaign:
                from app.services.campaigns import CampaignService

                await CampaignService.apply_campaign_to_lead(db, campaign.id, lead.id)
                await db.refresh(lead)
                history = list(lead.campaign_history or [])
                if not any(item.get("campaign_id") == campaign.id for item in history):
                    history.append({
                        "campaign_id": campaign.id,
                        "applied_at": datetime.now(timezone.utc).isoformat(),
                        "trigger": "won_referral",
                    })
                lead.campaign_history = history
                metadata = dict(lead.lead_metadata or {})
                metadata.update({
                    "referral_outreach_status": "sending",
                    "referral_outreach_route": "campaign",
                    "referral_campaign_id": campaign.id,
                })
                lead.lead_metadata = metadata
                await db.commit()

                try:
                    execute_campaign_for_lead.delay(campaign.id, lead.id)
                except Exception:
                    await db.refresh(lead)
                    failed_meta = dict(lead.lead_metadata or {})
                    failed_meta["referral_outreach_status"] = "failed"
                    failed_meta["referral_outreach_error"] = "campaign_enqueue_failed"
                    lead.lead_metadata = failed_meta
                    await db.commit()
                    raise

                await db.refresh(lead)
                active_meta = dict(lead.lead_metadata or {})
                active_meta["referral_outreach_status"] = "campaign_active"
                lead.lead_metadata = active_meta
                await db.commit()
                from app.services.shared import ActivityService
                await ActivityService.log_activity(
                    db,
                    lead_id=lead.id,
                    action_type="referral_outreach_started",
                    details={"route": "campaign", "campaign_id": campaign.id},
                )
                return

            target = await _delivery_target(db, lead)
            if not target:
                metadata = dict(lead.lead_metadata or {})
                metadata.update({
                    "referral_outreach_status": "unavailable",
                    "referral_outreach_route": "automatic",
                    "referral_outreach_error": "no_supported_channel",
                })
                lead.lead_metadata = metadata
                await db.commit()
                from app.services.shared import ActivityService
                await ActivityService.log_activity(
                    db,
                    lead_id=lead.id,
                    action_type="referral_outreach_unavailable",
                    details={"reason": "no_supported_channel"},
                )
                return

            provider_name, channel_user_id = target
            from app.services.chat.service import ChatService

            send_result = await ChatService.send_message(
                db=db,
                broker_id=broker_id,
                provider_name=provider_name,
                channel_user_id=channel_user_id,
                message_text=_default_referral_message(lead),
                lead_id=lead.id,
            )
            if not send_result.success:
                metadata = dict(lead.lead_metadata or {})
                metadata.update({
                    "referral_outreach_status": "failed",
                    "referral_outreach_error": send_result.error or "send_failed",
                })
                lead.lead_metadata = metadata
                await db.commit()
                raise RuntimeError(send_result.error or "Referral message could not be sent")

            await db.refresh(lead)
            metadata = dict(lead.lead_metadata or {})
            metadata.update({
                "referral_outreach_status": "asked",
                "referral_status": metadata.get("referral_status") or "pending",
                "referral_outreach_route": "automatic",
                "referral_outreach_channel": provider_name,
                "referral_asked_at": datetime.now(timezone.utc).isoformat(),
                "current_agent": "referral",
            })
            lead.lead_metadata = metadata
            await db.commit()
            from app.services.shared import ActivityService
            await ActivityService.log_activity(
                db,
                lead_id=lead.id,
                action_type="referral_outreach_started",
                details={"route": "automatic", "channel": provider_name},
            )

    async def _mark_failed(error: Exception) -> None:
        """Make infrastructure failures retryable instead of leaving a stuck claim."""
        from app.tasks.campaign_executor import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Lead).where(
                    Lead.id == lead_id,
                    Lead.broker_id == broker_id,
                )
            )
            lead = result.scalars().first()
            if not lead:
                return
            metadata = dict(lead.lead_metadata or {})
            if metadata.get("referral_outreach_status") == "sending":
                metadata["referral_outreach_status"] = "failed"
                metadata["referral_outreach_error"] = type(error).__name__
                lead.lead_metadata = metadata
                await db.commit()

    try:
        asyncio.run(_run())
    except Exception as exc:
        try:
            asyncio.run(_mark_failed(exc))
        except Exception as mark_exc:
            logger.error("Could not mark referral outreach as failed: %s", mark_exc)
        raise self.retry(exc=exc)
