"""
Celery task for processing inbound WhatsApp messages.

Uses DLQTask base to route final failures to the Dead Letter Queue.
"""
import asyncio
import logging

from celery import shared_task
from sqlalchemy.future import select

from app.config import settings
from app.tasks.base import DLQTask

logger = logging.getLogger(__name__)


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
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        # Create a fresh engine per task invocation — avoids asyncpg event-loop
        # conflicts when asyncio.run() is called inside forked Celery workers.
        _engine = create_async_engine(settings.DATABASE_URL, echo=False)
        AsyncSessionLocal = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

        pid = str(phone_number_id)

        logger.info(
            "WhatsApp task starting: from=%s phone_number_id=%s wamid=%s",
            from_number, pid, wamid,
        )

        from app.models.broker_chat_config import BrokerChatConfig
        from app.models.chat_message import MessageStatus
        from app.schemas.lead import LeadCreate
        from app.services.chat.base_provider import ChatMessageData
        from app.services.chat.orchestrator import ChatOrchestratorService
        from app.services.chat.service import ChatService
        from app.services.chat.whatsapp_service import WhatsAppService
        from app.services.leads import LeadService

        async with AsyncSessionLocal() as db:
            # 1. Resolve broker via phone_number_id stored in BrokerChatConfig JSONB.
            #    Guard against NULL provider_configs with isnot(None) filter.
            result = await db.execute(
                select(BrokerChatConfig).where(
                    BrokerChatConfig.provider_configs.isnot(None),
                    BrokerChatConfig.provider_configs["whatsapp"]["phone_number_id"].astext
                    == pid,
                )
            )
            config = result.scalars().first()

            # Fallback: if global env-var matches, use any broker_chat_config with
            # whatsapp enabled (legacy single-broker setup without per-broker DB config).
            if not config and settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_PHONE_NUMBER_ID == pid:
                fallback = await db.execute(
                    select(BrokerChatConfig).where(
                        BrokerChatConfig.enabled_providers.contains(["whatsapp"])
                    ).limit(1)
                )
                config = fallback.scalars().first()

            if not config:
                logger.warning(
                    "WhatsApp task: no BrokerChatConfig found for phone_number_id=%s. "
                    "Configure the broker WhatsApp channel in the Superadmin panel.",
                    pid,
                )
                return
            broker_id = config.broker_id
            logger.info("WhatsApp task: resolved broker_id=%s for phone_number_id=%s", broker_id, pid)

            # Extract per-broker WA credentials (fall back to global env vars if not set)
            _wa_cfg = (config.provider_configs or {}).get("whatsapp", {})
            _wa_phone_id = _wa_cfg.get("phone_number_id") or pid
            _wa_token = _wa_cfg.get("access_token")
            logger.info(
                "WhatsApp task: credentials source=%s",
                "db" if _wa_token else "env-vars",
            )

            # 2. Find or create lead
            lead = await ChatService.find_lead_by_channel(
                db, broker_id, "whatsapp", from_number
            )
            if not lead:
                logger.info("WhatsApp task: creating new lead for from_number=%s", from_number)
                lead = await LeadService.create_lead(
                    db,
                    LeadCreate(
                        phone=from_number,
                        name="WhatsApp Contact",
                        tags=["whatsapp", "inbound"],
                    ),
                    broker_id=broker_id,
                )
            logger.info("WhatsApp task: using lead_id=%s", lead.id)

            # G6: Idempotency check — if this wamid was already processed (e.g.
            # Meta retried after a timeout), skip re-processing to prevent duplicate
            # AI responses and state corruption.
            # Guard: only check when wamid is non-empty; `== None` generates IS NULL
            # which would match unrelated rows with no channel_message_id.
            if wamid:
                from app.models.chat_message import ChatMessage as _CMCheck
                from sqlalchemy.future import select as _sel_dup
                _dup_res = await db.execute(
                    _sel_dup(_CMCheck.id)
                    .where(_CMCheck.channel_message_id == wamid)
                    .limit(1)
                )
                if _dup_res.scalars().first():
                    logger.info(
                        "WhatsApp task: wamid=%s already processed — skipping (idempotent)", wamid
                    )
                    return

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
                        "phone_number_id": pid,
                    },
                ),
                status=MessageStatus.DELIVERED,
                ai_used=False,
            )
            logger.info("WhatsApp task: inbound message logged, running AI orchestrator")

            # 4. Run AI orchestrator (message already logged above — skip double log)
            logger.info("WhatsApp task: starting AI orchestrator for lead_id=%s", lead.id)
            try:
                chat_result = await ChatOrchestratorService.process_chat_message(
                    db=db,
                    current_user={"broker_id": broker_id, "id": None},
                    message=message_text,
                    lead_id=lead.id,
                    provider_name="whatsapp",
                    skip_inbound_log=True,
                )
            except Exception as _orch_exc:
                logger.error(
                    "WhatsApp task: orchestrator FAILED for lead_id=%s: %s",
                    lead.id, _orch_exc, exc_info=True,
                )
                raise
            logger.info(
                "WhatsApp task: orchestrator done, response_len=%d response=%r",
                len(chat_result.response or ""),
                (chat_result.response or "")[:80],
            )

            # 5. Send AI reply (skip if human agent has taken control)
            if chat_result.response and chat_result.response != "[human_mode]":
                logger.info("WhatsApp task: sending reply to %s via phone_number_id=%s", from_number, _wa_phone_id)
                wa = WhatsAppService(phone_number_id=_wa_phone_id, access_token=_wa_token)
                try:
                    await wa.send_text_message(from_number, chat_result.response)
                except Exception as _send_exc:
                    logger.error("WhatsApp task: send_text_message FAILED: %s", _send_exc, exc_info=True)
                    raise
                logger.info("WhatsApp task: reply sent to %s", from_number)
            elif chat_result.response == "[human_mode]":
                logger.info("WhatsApp task: human_mode active, skipping AI reply for %s", from_number)
            else:
                logger.warning("WhatsApp task: empty response from orchestrator for lead_id=%s", lead.id)

            # 6. Mark original message as read
            wa = WhatsAppService(phone_number_id=_wa_phone_id, access_token=_wa_token)
            try:
                await wa.mark_as_read(wamid)
            except Exception as _read_exc:
                logger.warning("WhatsApp task: mark_as_read FAILED (non-fatal): %s", _read_exc)
            logger.info("WhatsApp task: completed successfully for wamid=%s", wamid)

        try:
            await _engine.dispose()
        except Exception:
            pass

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
