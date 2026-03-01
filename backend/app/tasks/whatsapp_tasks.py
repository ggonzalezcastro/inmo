"""
Celery task for processing inbound WhatsApp messages.

Uses DLQTask base to route final failures to the Dead Letter Queue.
"""
import asyncio
import logging

from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select

from app.config import settings
from app.tasks.base import DLQTask

logger = logging.getLogger(__name__)

# Dedicated async engine for Celery workers (separate from the FastAPI engine)
_engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(
    name="app.tasks.whatsapp_tasks.process_whatsapp_message",
    base=DLQTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_whatsapp_message(
    self,
    from_number: str,
    message_text: str,
    wamid: str,
    phone_number_id: str,
):
    """Orchestrate a full WhatsApp inbound message cycle."""

    async def _run():
        from app.models.broker_chat_config import BrokerChatConfig
        from app.models.chat_message import MessageStatus
        from app.schemas.lead import LeadCreate
        from app.services.chat.base_provider import ChatMessageData
        from app.services.chat.orchestrator import ChatOrchestratorService
        from app.services.chat.service import ChatService
        from app.services.chat.whatsapp_service import WhatsAppService
        from app.services.leads import LeadService

        async with AsyncSessionLocal() as db:
            # 1. Resolve broker via phone_number_id stored in BrokerChatConfig JSONB
            result = await db.execute(
                select(BrokerChatConfig).where(
                    BrokerChatConfig.provider_configs["whatsapp"]["phone_number_id"].astext
                    == phone_number_id
                )
            )
            config = result.scalars().first()
            if not config:
                logger.warning(
                    "WhatsApp task: no broker found for phone_number_id=%s", phone_number_id
                )
                return
            broker_id = config.broker_id

            # 2. Find or create lead
            lead = await ChatService.find_lead_by_channel(
                db, broker_id, "whatsapp", from_number
            )
            if not lead:
                lead = await LeadService.create_lead(
                    db,
                    LeadCreate(
                        phone=from_number,
                        name="WhatsApp Contact",
                        tags=["whatsapp", "inbound"],
                    ),
                    broker_id=broker_id,
                )

            # 3. Log inbound message
            await ChatService.log_message(
                db=db,
                lead_id=lead.id,
                broker_id=broker_id,
                provider_name="whatsapp",
                message_data=ChatMessageData(
                    channel_user_id=from_number,
                    channel_username=None,
                    channel_message_id=wamid,
                    message_text=message_text,
                    direction="in",
                    provider_metadata={
                        "wamid": wamid,
                        "phone_number_id": phone_number_id,
                    },
                ),
                status=MessageStatus.DELIVERED,
                ai_used=False,
            )

            # 4. Run AI orchestrator
            chat_result = await ChatOrchestratorService.process_chat_message(
                db=db,
                current_user={"broker_id": broker_id, "id": None},
                message=message_text,
                lead_id=lead.id,
                provider_name="whatsapp",
            )

            # 5. Send AI reply
            wa = WhatsAppService()
            await wa.send_text_message(from_number, chat_result.response)

            # 6. Mark original message as read
            await wa.mark_as_read(wamid)

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(
            "WhatsApp task failed (attempt %d): %s",
            self.request.retries + 1,
            exc,
            exc_info=True,
        )
        raise self.retry(exc=exc)
