"""
Base Chat Provider - abstract interface for all chat/messaging providers.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class ChatMessageData:
    """Normalized message data for any provider."""

    channel_user_id: str
    channel_username: Optional[str]
    channel_message_id: Optional[str]
    message_text: str
    direction: str  # "in" or "out"
    provider_metadata: Optional[Dict[str, Any]] = None
    attachments: Optional[List[Dict[str, Any]]] = None


@dataclass
class SendMessageResult:
    """Result of sending a message."""

    success: bool
    message_id: Optional[str]
    error: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None


class BaseChatProvider(ABC):
    """Base class for all chat providers (Telegram, WhatsApp, Instagram, etc.)."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize provider with configuration.

        Args:
            config: Provider-specific configuration (from BrokerChatConfig.provider_configs)
        """
        self.config = config

    @abstractmethod
    async def send_message(
        self,
        channel_user_id: str,
        message_text: str,
        **kwargs: Any
    ) -> SendMessageResult:
        """
        Send message to user.

        Args:
            channel_user_id: User ID in the channel (telegram_id, phone number, etc.)
            message_text: Message content
            **kwargs: Provider-specific options (reply_to, parse_mode, etc.)

        Returns:
            SendMessageResult with success status and message_id
        """
        pass

    @abstractmethod
    async def send_media(
        self,
        channel_user_id: str,
        media_url: str,
        media_type: str,  # "image", "video", "audio", "document"
        caption: Optional[str] = None,
        **kwargs: Any
    ) -> SendMessageResult:
        """Send media message."""
        pass

    @abstractmethod
    async def set_webhook(self, webhook_url: str, **kwargs: Any) -> Dict[str, Any]:
        """Configure webhook for receiving messages."""
        pass

    @abstractmethod
    async def delete_webhook(self) -> Dict[str, Any]:
        """Remove webhook configuration."""
        pass

    @abstractmethod
    async def get_webhook_info(self) -> Dict[str, Any]:
        """Get current webhook configuration."""
        pass

    @abstractmethod
    async def parse_webhook_message(self, payload: Dict[str, Any]) -> Optional[ChatMessageData]:
        """
        Parse incoming webhook payload into normalized ChatMessageData.

        Args:
            payload: Raw webhook payload from provider

        Returns:
            ChatMessageData if valid message, None otherwise
        """
        pass

    @abstractmethod
    async def verify_webhook_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """
        Verify webhook signature for security.

        Args:
            payload: Webhook payload
            signature: Signature from provider (usually in headers)

        Returns:
            True if signature is valid
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider name (telegram, whatsapp, etc.)."""
        pass
