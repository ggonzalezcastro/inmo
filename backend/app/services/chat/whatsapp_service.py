"""
Stateless WhatsApp Cloud API service using global env-var credentials.

Distinct from WhatsAppProvider (which is DB-backed per-broker).
Used by whatsapp_tasks to send replies and mark messages as read.
"""
import logging
from typing import Any, Dict

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Minimal WhatsApp Cloud API client for outbound operations."""

    BASE_URL = "https://graph.facebook.com/v18.0"

    def _api_url(self) -> str:
        return f"{self.BASE_URL}/{settings.WHATSAPP_PHONE_NUMBER_ID}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
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
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self._api_url()}/messages",
                headers=self._headers(),
                json=payload,
            )
        if response.status_code != 200:
            logger.error("WhatsApp send_text_message failed: %s", response.text)
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
