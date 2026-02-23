"""
WhatsApp Business API (Meta) chat provider.
"""
import hmac
import hashlib
import json
import logging
from typing import Optional, Dict, Any, List

import httpx

from app.services.chat.base_provider import (
    BaseChatProvider,
    ChatMessageData,
    SendMessageResult,
)

logger = logging.getLogger(__name__)


class WhatsAppProvider(BaseChatProvider):
    """WhatsApp Business API provider (Meta)."""

    BASE_URL = "https://graph.facebook.com"
    API_VERSION = "v18.0"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.phone_number_id = config.get("phone_number_id")
        self.access_token = config.get("access_token")
        self.verify_token = config.get("verify_token")
        self.app_secret = config.get("app_secret")

        if not all([self.phone_number_id, self.access_token]):
            raise ValueError("WhatsApp phone_number_id and access_token are required")

        self.api_url = f"{self.BASE_URL}/{self.API_VERSION}/{self.phone_number_id}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def send_message(
        self,
        channel_user_id: str,
        message_text: str,
        **kwargs: Any
    ) -> SendMessageResult:
        """Send text message via WhatsApp."""
        try:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": channel_user_id.replace("+", "").replace(" ", ""),
                "type": "text",
                "text": {
                    "preview_url": kwargs.get("preview_url", False),
                    "body": message_text,
                },
            }
            if context_message_id := kwargs.get("context_message_id"):
                payload["context"] = {"message_id": context_message_id}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/messages",
                    headers=self._headers(),
                    json=payload,
                )

                if response.status_code == 200:
                    result = response.json()
                    message_id = result["messages"][0]["id"]
                    return SendMessageResult(
                        success=True,
                        message_id=message_id,
                        provider_response=result,
                    )
                error = response.text
                logger.error("WhatsApp send failed: %s", error)
                return SendMessageResult(
                    success=False,
                    message_id=None,
                    error=error,
                )
        except Exception as e:
            logger.error("Error sending WhatsApp message: %s", e, exc_info=True)
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
        """Send media via WhatsApp."""
        try:
            type_map = {
                "image": "image",
                "video": "video",
                "audio": "audio",
                "document": "document",
            }
            wa_type = type_map.get(media_type, "document")

            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": channel_user_id.replace("+", "").replace(" ", ""),
                "type": wa_type,
                wa_type: {"link": media_url},
            }
            if caption and wa_type in ("image", "video", "document"):
                payload[wa_type]["caption"] = caption

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/messages",
                    headers=self._headers(),
                    json=payload,
                )

                if response.status_code == 200:
                    result = response.json()
                    message_id = result["messages"][0]["id"]
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
            logger.error("Error sending WhatsApp media: %s", e, exc_info=True)
            return SendMessageResult(
                success=False,
                message_id=None,
                error=str(e),
            )

    async def set_webhook(self, webhook_url: str, **kwargs: Any) -> Dict[str, Any]:
        """WhatsApp webhooks are configured at the App level in Meta Business Suite."""
        return {
            "message": "WhatsApp webhooks must be configured in Meta Business Suite",
            "steps": [
                "Go to Meta Business Suite",
                "Select your app",
                "Configure Webhooks with callback URL and verify token",
                "Subscribe to 'messages' webhook",
            ],
            "webhook_url": webhook_url,
            "verify_token": self.verify_token,
        }

    async def delete_webhook(self) -> Dict[str, Any]:
        """WhatsApp webhooks are managed in Meta Business Suite."""
        return {"message": "Manage webhooks in Meta Business Suite"}

    async def get_webhook_info(self) -> Dict[str, Any]:
        """WhatsApp webhooks are managed in Meta Business Suite."""
        return {"message": "Check webhook configuration in Meta Business Suite"}

    async def parse_webhook_message(self, payload: Dict[str, Any]) -> Optional[ChatMessageData]:
        """
        Parse WhatsApp webhook payload.
        Structure: {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"messages": [...]}}]}]}
        """
        try:
            entry = payload.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])

            if not messages:
                return None

            message = messages[0]
            message_type = message.get("type", "")

            message_text = ""
            if message_type == "text":
                message_text = message.get("text", {}).get("body", "")
            elif message_type == "button":
                message_text = message.get("button", {}).get("text", "")
            elif message_type == "interactive":
                interactive = message.get("interactive", {})
                if interactive.get("type") == "button_reply":
                    message_text = interactive.get("button_reply", {}).get("title", "")
                elif interactive.get("type") == "list_reply":
                    message_text = interactive.get("list_reply", {}).get("title", "")

            return ChatMessageData(
                channel_user_id=message.get("from", ""),
                channel_username=None,
                channel_message_id=message.get("id"),
                message_text=message_text,
                direction="in",
                provider_metadata={
                    "phone_number_id": value.get("metadata", {}).get("phone_number_id"),
                    "message_type": message_type,
                    "timestamp": message.get("timestamp"),
                    "context": message.get("context"),
                },
                attachments=self._extract_attachments(message),
            )
        except Exception as e:
            logger.error("Error parsing WhatsApp webhook: %s", e, exc_info=True)
            return None

    def _extract_attachments(self, message: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract media attachments from WhatsApp message."""
        message_type = message.get("type")
        if message_type not in ("image", "video", "audio", "document", "sticker"):
            return None
        media = message.get(message_type, {})
        return [{
            "type": message_type,
            "id": media.get("id"),
            "mime_type": media.get("mime_type"),
            "sha256": media.get("sha256"),
            "caption": media.get("caption"),
        }]

    async def verify_webhook_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        """
        Verify WhatsApp webhook signature using app_secret.
        Signature is in X-Hub-Signature-256 header, format: sha256=<signature>
        """
        if not self.app_secret:
            logger.warning("WhatsApp app_secret not configured, skipping signature verification")
            return True

        try:
            signature = signature.replace("sha256=", "").strip()
            payload_str = json.dumps(payload, separators=(",", ":"), sort_keys=True)
            expected = hmac.new(
                self.app_secret.encode("utf-8"),
                payload_str.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(signature, expected)
        except Exception as e:
            logger.error("Error verifying WhatsApp signature: %s", e, exc_info=True)
            return False

    def get_provider_name(self) -> str:
        return "whatsapp"
