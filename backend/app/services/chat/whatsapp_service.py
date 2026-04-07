"""
Stateless WhatsApp Cloud API service.

Supports both global env-var credentials (legacy) and per-broker credentials
loaded from BrokerChatConfig.provider_configs (multi-broker setup).
Used by whatsapp_tasks to send replies and mark messages as read.
"""
import logging
from typing import Any, Dict, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Minimal WhatsApp Cloud API client for outbound operations."""

    BASE_URL = "https://graph.facebook.com/v18.0"

    def __init__(
        self,
        phone_number_id: Optional[str] = None,
        access_token: Optional[str] = None,
    ):
        """
        Initialise with explicit credentials (per-broker) or fall back to global env vars.
        Pass phone_number_id and access_token from BrokerChatConfig.provider_configs["whatsapp"]
        when available to avoid relying on global env vars.
        """
        self._phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
        self._access_token = access_token or settings.WHATSAPP_ACCESS_TOKEN

        if not self._phone_number_id:
            logger.warning("WhatsAppService: phone_number_id is not set — messages will fail")
        if not self._access_token:
            logger.warning("WhatsAppService: access_token is not set — messages will fail")

    def _api_url(self) -> str:
        return f"{self.BASE_URL}/{self._phone_number_id}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def send_text_message(self, to: str, text: str) -> Dict[str, Any]:
        """Send a plain-text WhatsApp message."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        logger.info(
            "WhatsApp sending to=%s via phone_number_id=%s text=%r",
            to, self._phone_number_id, text[:60],
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._api_url()}/messages",
                headers=self._headers(),
                json=payload,
            )
        if response.status_code != 200:
            logger.error(
                "WhatsApp send_text_message FAILED status=%s body=%s",
                response.status_code, response.text,
            )
        else:
            logger.info("WhatsApp send_text_message OK to=%s", to)
        return response.json()

    async def mark_as_read(self, wamid: str) -> Dict[str, Any]:
        """Mark an inbound message as read."""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": wamid,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._api_url()}/messages",
                headers=self._headers(),
                json=payload,
            )
        if response.status_code != 200:
            logger.error("WhatsApp mark_as_read failed: %s", response.text)
        return response.json()
