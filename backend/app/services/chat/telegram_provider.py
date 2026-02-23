"""
Telegram Bot API chat provider.
"""
import httpx
import logging
from typing import Optional, Dict, Any, List

from app.services.chat.base_provider import (
    BaseChatProvider,
    ChatMessageData,
    SendMessageResult,
)

logger = logging.getLogger(__name__)


class TelegramProvider(BaseChatProvider):
    """Telegram Bot API provider implementation."""

    BASE_URL = "https://api.telegram.org"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bot_token = config.get("bot_token")
        if not self.bot_token:
            raise ValueError("Telegram bot_token is required")
        self.api_url = f"{self.BASE_URL}/bot{self.bot_token}"
        self.webhook_secret = config.get("webhook_secret")

    async def send_message(
        self,
        channel_user_id: str,
        message_text: str,
        **kwargs: Any
    ) -> SendMessageResult:
        """Send text message via Telegram."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "chat_id": int(channel_user_id),
                    "text": message_text,
                    "parse_mode": kwargs.get("parse_mode", "HTML"),
                }
                if reply_to := kwargs.get("reply_to_message_id"):
                    payload["reply_to_message_id"] = reply_to

                response = await client.post(
                    f"{self.api_url}/sendMessage",
                    json=payload,
                )

                if response.status_code == 200:
                    result = response.json()
                    message_id = str(result["result"]["message_id"])
                    return SendMessageResult(
                        success=True,
                        message_id=message_id,
                        provider_response=result,
                    )
                error_text = response.text
                logger.error("Telegram send failed: %s", error_text)
                return SendMessageResult(
                    success=False,
                    message_id=None,
                    error=error_text,
                )
        except Exception as e:
            logger.error("Error sending Telegram message: %s", e, exc_info=True)
            return SendMessageResult(
                success=False,
                message_id=None,
                error=str(e),
            )

    async def send_media(
        self,
        channel_user_id: str,
        media_url: str,
        media_type: str,
        caption: Optional[str] = None,
        **kwargs: Any
    ) -> SendMessageResult:
        """Send media via Telegram."""
        try:
            method_map = {
                "image": "sendPhoto",
                "video": "sendVideo",
                "audio": "sendAudio",
                "document": "sendDocument",
            }
            field_map = {
                "image": "photo",
                "video": "video",
                "audio": "audio",
                "document": "document",
            }
            method = method_map.get(media_type, "sendDocument")
            field = field_map.get(media_type, "document")

            async with httpx.AsyncClient() as client:
                payload = {
                    "chat_id": int(channel_user_id),
                    field: media_url,
                }
                if caption:
                    payload["caption"] = caption

                response = await client.post(
                    f"{self.api_url}/{method}",
                    json=payload,
                )

                if response.status_code == 200:
                    result = response.json()
                    message_id = str(result["result"]["message_id"])
                    return SendMessageResult(
                        success=True,
                        message_id=message_id,
                        provider_response=result,
                    )
                return SendMessageResult(
                    success=False,
                    message_id=None,
                    error=response.text,
                )
        except Exception as e:
            logger.error("Error sending Telegram media: %s", e, exc_info=True)
            return SendMessageResult(
                success=False,
                message_id=None,
                error=str(e),
            )

    async def set_webhook(self, webhook_url: str, **kwargs: Any) -> Dict[str, Any]:
        """Set Telegram webhook."""
        async with httpx.AsyncClient() as client:
            payload = {"url": webhook_url}
            if self.webhook_secret:
                payload["secret_token"] = self.webhook_secret
            response = await client.post(
                f"{self.api_url}/setWebhook",
                json=payload,
            )
            return response.json()

    async def delete_webhook(self) -> Dict[str, Any]:
        """Delete Telegram webhook."""
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.api_url}/deleteWebhook")
            return response.json()

    async def get_webhook_info(self) -> Dict[str, Any]:
        """Get Telegram webhook info."""
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self.api_url}/getWebhookInfo")
            return response.json()

    async def parse_webhook_message(self, payload: Dict[str, Any]) -> Optional[ChatMessageData]:
        """
        Parse Telegram webhook payload.
        Structure: {"update_id": N, "message": {"message_id": N, "from": {...}, "chat": {...}, "text": "...", ...}}
        """
        message = payload.get("message")
        if not message:
            return None

        from_user = message.get("from", {})
        text = message.get("text") or ""

        return ChatMessageData(
            channel_user_id=str(from_user.get("id", "")),
            channel_username=from_user.get("username"),
            channel_message_id=str(message.get("message_id", "")),
            message_text=text,
            direction="in",
            provider_metadata={
                "chat_id": message.get("chat", {}).get("id"),
                "message_type": "text" if text else "other",
                "date": message.get("date"),
                "from": from_user,
            },
            attachments=self._extract_attachments(message),
        )

    def _extract_attachments(self, message: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract media attachments from Telegram message."""
        attachments = []
        for media_type in ("photo", "video", "audio", "document", "voice", "sticker"):
            if media_type not in message:
                continue
            media = message[media_type]
            if media_type == "photo" and isinstance(media, list):
                media = media[-1] if media else {}
            attachments.append({
                "type": media_type,
                "file_id": media.get("file_id"),
                "file_size": media.get("file_size"),
                "mime_type": media.get("mime_type"),
            })
        return attachments if attachments else None

    async def verify_webhook_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """
        Verify Telegram webhook signature.
        Telegram uses X-Telegram-Bot-Api-Secret-Token header when secret_token is set.
        """
        if not self.webhook_secret:
            return True
        return signature == self.webhook_secret

    def get_provider_name(self) -> str:
        return "telegram"
