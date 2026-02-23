"""
Chat service - orchestrates chat providers and message persistence.
"""
import logging
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.broker_chat_config import BrokerChatConfig
from app.models.chat_message import ChatMessage, ChatProvider, MessageDirection, MessageStatus
from app.services.chat.base_provider import BaseChatProvider, ChatMessageData, SendMessageResult
from app.services.chat.factory import ChatProviderFactory
from app.services.leads import LeadService
from app.schemas.lead import LeadCreate

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing chat messages across providers."""

    @staticmethod
    async def get_broker_chat_config(
        db: AsyncSession,
        broker_id: int,
    ) -> Optional[BrokerChatConfig]:
        """Get chat configuration for broker."""
        result = await db.execute(
            select(BrokerChatConfig).where(BrokerChatConfig.broker_id == broker_id)
        )
        return result.scalars().first()

    @staticmethod
    async def get_provider_for_broker(
        db: AsyncSession,
        broker_id: int,
        provider_name: str,
    ) -> Optional[BaseChatProvider]:
        """Get chat provider instance for broker."""
        config = await ChatService.get_broker_chat_config(db, broker_id)
        if not config:
            logger.warning("No chat config found for broker %s", broker_id)
            return None

        enabled = config.enabled_providers or []
        if provider_name not in enabled:
            logger.warning("Provider %s not enabled for broker %s", provider_name, broker_id)
            return None

        provider_configs = config.provider_configs or {}
        provider_config = provider_configs.get(provider_name)
        if not provider_config:
            logger.warning("No config found for provider %s", provider_name)
            return None

        try:
            return ChatProviderFactory.create(provider_name, provider_config)
        except Exception as e:
            logger.error("Error creating provider %s: %s", provider_name, e, exc_info=True)
            return None

    @staticmethod
    async def send_message(
        db: AsyncSession,
        broker_id: int,
        provider_name: str,
        channel_user_id: str,
        message_text: str,
        lead_id: Optional[int] = None,
        **kwargs: Any
    ) -> SendMessageResult:
        """
        Send message via specified provider.
        Optionally logs the outbound message to DB when lead_id is provided.
        """
        provider = await ChatService.get_provider_for_broker(db, broker_id, provider_name)
        if not provider:
            return SendMessageResult(
                success=False,
                message_id=None,
                error=f"Provider {provider_name} not available",
            )

        result = await provider.send_message(channel_user_id, message_text, **kwargs)

        if result.success and lead_id:
            await ChatService.log_message(
                db=db,
                lead_id=lead_id,
                broker_id=broker_id,
                provider_name=provider_name,
                message_data=ChatMessageData(
                    channel_user_id=channel_user_id,
                    channel_username=None,
                    channel_message_id=result.message_id,
                    message_text=message_text,
                    direction="out",
                    provider_metadata=result.provider_response,
                ),
                status=MessageStatus.SENT,
            )

        return result

    @staticmethod
    async def log_message(
        db: AsyncSession,
        lead_id: int,
        broker_id: int,
        provider_name: str,
        message_data: ChatMessageData,
        status: MessageStatus = MessageStatus.SENT,
        ai_used: bool = True,
    ) -> ChatMessage:
        """Log chat message to database."""
        try:
            provider_enum = ChatProvider(provider_name)
        except ValueError:
            provider_enum = ChatProvider.WEBCHAT

        message = ChatMessage(
            lead_id=lead_id,
            broker_id=broker_id,
            provider=provider_enum,
            channel_user_id=message_data.channel_user_id,
            channel_username=message_data.channel_username,
            channel_message_id=message_data.channel_message_id,
            message_text=message_data.message_text,
            direction=(
                MessageDirection.INBOUND
                if message_data.direction == "in"
                else MessageDirection.OUTBOUND
            ),
            status=status,
            provider_metadata=message_data.provider_metadata,
            attachments=message_data.attachments,
            ai_response_used=ai_used,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        return message

    @staticmethod
    async def find_lead_by_channel(
        db: AsyncSession,
        broker_id: int,
        provider_name: str,
        channel_user_id: str,
    ) -> Optional[Any]:
        """Find lead that has messages from this channel user (provider + channel_user_id)."""
        try:
            provider_enum = ChatProvider(provider_name)
        except ValueError:
            provider_enum = ChatProvider.WEBCHAT

        result = await db.execute(
            select(ChatMessage.lead_id)
            .where(
                ChatMessage.broker_id == broker_id,
                ChatMessage.provider == provider_enum,
                ChatMessage.channel_user_id == channel_user_id,
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        row = result.first()
        if not row:
            return None
        return await LeadService.get_lead(db, row[0])

    @staticmethod
    async def handle_webhook(
        db: AsyncSession,
        broker_id: int,
        provider_name: str,
        payload: Dict[str, Any],
        signature: Optional[str] = None,
    ) -> Optional[ChatMessage]:
        """
        Handle incoming webhook from provider.
        Verifies signature if provided, parses message, finds/creates lead, logs message.
        """
        provider = await ChatService.get_provider_for_broker(db, broker_id, provider_name)
        if not provider:
            logger.error("Provider %s not available for broker %s", provider_name, broker_id)
            return None

        if signature:
            is_valid = await provider.verify_webhook_signature(payload, signature)
            if not is_valid:
                logger.error("Invalid webhook signature for %s", provider_name)
                return None

        message_data = await provider.parse_webhook_message(payload)
        if not message_data:
            logger.debug("No message data extracted from webhook")
            return None

        lead = await ChatService.find_lead_by_channel(
            db, broker_id, provider_name, message_data.channel_user_id
        )
        if not lead:
            phone = (
                message_data.channel_user_id
                if provider_name == "whatsapp"
                else f"{provider_name}_{message_data.channel_user_id}"
            )
            lead_data = LeadCreate(
                phone=phone,
                name=message_data.channel_username or "New Contact",
                tags=[provider_name, "inbound"],
            )
            lead = await LeadService.create_lead(db, lead_data, broker_id=broker_id)

        chat_message = await ChatService.log_message(
            db=db,
            lead_id=lead.id,
            broker_id=broker_id,
            provider_name=provider_name,
            message_data=message_data,
            status=MessageStatus.DELIVERED,
            ai_used=False,
        )
        return chat_message
