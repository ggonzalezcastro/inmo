"""Instagram professional messaging provider backed by Meta Graph API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.chat.base_provider import BaseChatProvider, ChatMessageData, SendMessageResult
from app.services.meta.client import MetaGraphClient, MetaGraphError


class InstagramProvider(BaseChatProvider):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.asset_id = str(config.get("asset_id") or "")
        self.access_token = config.get("access_token")
        if not self.asset_id or not self.access_token:
            raise ValueError("Instagram asset_id and access_token are required")
        self.client = MetaGraphClient(
            access_token=self.access_token,
            app_secret=settings.META_INSTAGRAM_APP_SECRET,
            base_url="https://graph.instagram.com",
        )

    async def send_message(self, channel_user_id: str, message_text: str, **kwargs: Any) -> SendMessageResult:
        try:
            payload = await self.client.post(
                f"{self.asset_id}/messages",
                json={"recipient": {"id": channel_user_id}, "message": {"text": message_text}},
            )
            return SendMessageResult(True, payload.get("message_id"), provider_response=payload)
        except MetaGraphError as exc:
            return SendMessageResult(False, None, error=str(exc))

    async def send_media(
        self,
        channel_user_id: str,
        media_url: str,
        media_type: str,
        caption: Optional[str] = None,
        **kwargs: Any,
    ) -> SendMessageResult:
        try:
            payload = await self.client.post(
                f"{self.asset_id}/messages",
                json={
                    "recipient": {"id": channel_user_id},
                    "message": {"attachment": {"type": media_type, "payload": {"url": media_url}}},
                },
            )
            return SendMessageResult(True, payload.get("message_id"), provider_response=payload)
        except MetaGraphError as exc:
            return SendMessageResult(False, None, error=str(exc))

    async def set_webhook(self, webhook_url: str, **kwargs: Any) -> Dict[str, Any]:
        return {"webhook_url": webhook_url, "managed_at_app_level": True}

    async def delete_webhook(self) -> Dict[str, Any]:
        return {"managed_at_app_level": True}

    async def get_webhook_info(self) -> Dict[str, Any]:
        return {"managed_at_app_level": True}

    async def parse_webhook_message(self, payload: Dict[str, Any]) -> Optional[ChatMessageData]:
        try:
            event = payload["entry"][0]["messaging"][0]
            message = event.get("message") or {}
            if not message or message.get("is_echo"):
                return None
            attachments: Optional[List[Dict[str, Any]]] = message.get("attachments")
            return ChatMessageData(
                channel_user_id=str(event["sender"]["id"]),
                channel_username=None,
                channel_message_id=message.get("mid"),
                message_text=message.get("text") or "",
                direction="in",
                provider_metadata={"recipient_id": event.get("recipient", {}).get("id")},
                attachments=attachments,
            )
        except (KeyError, IndexError, TypeError):
            return None

    async def verify_webhook_signature(self, payload: Dict[str, Any], signature: str) -> bool:
        return True  # verified once by the global Meta webhook before provider dispatch

    def get_provider_name(self) -> str:
        return "instagram"
