"""
Bland AI voice provider - implements BaseVoiceProvider.
See https://docs.bland.ai/ for API details.
"""
import logging
from typing import Dict, Any, Optional

import aiohttp

from app.config import settings
from app.services.voice.base_provider import BaseVoiceProvider
from app.services.voice.types import (
    MakeCallRequest,
    CallStatusResult,
    WebhookEvent,
    CallEventType,
    VoiceProviderType,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.bland.ai/v1"


class BlandProvider(BaseVoiceProvider):
    """Bland AI voice provider."""

    def __init__(self):
        self.api_key = getattr(settings, "BLAND_API_KEY", None) or ""
        if not self.api_key:
            logger.warning("Bland API key not configured")

    def get_provider_type(self) -> VoiceProviderType:
        return VoiceProviderType.BLAND

    async def make_call(self, request: MakeCallRequest) -> str:
        """Start outbound call via Bland AI. Returns external_call_id (call_id)."""
        if not self.api_key:
            raise ValueError("Bland API key not configured")

        task = request.system_prompt or request.first_message or "Introduce yourself and assist the customer."
        webhook_url = request.webhook_url or ""

        payload = {
            "phone_number": request.phone_number,
            "task": task,
        }
        if webhook_url:
            payload["webhook"] = webhook_url
        if request.first_message:
            payload["first_sentence"] = request.first_message

        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/calls",
                json=payload,
                headers=headers,
            ) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    logger.error("Bland API error: %s - %s", response.status, error_text)
                    raise ValueError(f"Failed to create call: {error_text}")

                data = await response.json()
                if data.get("status") != "success":
                    raise ValueError(data.get("message", "Bland API returned error"))

                call_id = data.get("call_id")
                if not call_id:
                    raise ValueError("Bland API did not return call_id")
                logger.info("Bland call initiated: %s to %s", call_id, request.phone_number)
                return call_id

    async def get_call_status(self, external_call_id: str) -> CallStatusResult:
        """Get call status from Bland AI."""
        if not self.api_key:
            raise ValueError("Bland API key not configured")

        headers = {"Authorization": self.api_key}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/calls/{external_call_id}",
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"Failed to get call status: {error_text}")

                data = await response.json()
                status = data.get("status", "unknown")
                duration = data.get("duration_seconds") or data.get("call_length")
                return CallStatusResult(
                    external_call_id=external_call_id,
                    status=status,
                    duration_seconds=int(duration) if duration is not None else None,
                    transcript=data.get("transcript") or data.get("concatenated_transcript"),
                    recording_url=data.get("recording_url") or data.get("recording"),
                )

    async def handle_webhook(self, payload: dict, headers: dict = None) -> WebhookEvent:
        """
        Parse Bland AI webhook payload into WebhookEvent.
        Bland may send different shapes; this normalizes common fields.
        """
        call_id = payload.get("call_id") or payload.get("id") or ""
        status = payload.get("status") or payload.get("call_status")
        transcript = payload.get("transcript") or payload.get("concatenated_transcript")
        summary = payload.get("summary") or payload.get("analysis")
        recording_url = payload.get("recording_url") or payload.get("recording")
        duration = payload.get("duration_seconds") or payload.get("call_length")

        event_type = CallEventType.STATUS_UPDATE
        if status in ("completed", "ended", "done"):
            event_type = CallEventType.CALL_ENDED
        elif status in ("failed", "busy", "no-answer"):
            event_type = CallEventType.CALL_FAILED
        elif status == "in-progress":
            event_type = CallEventType.CALL_ANSWERED
        elif status == "ringing":
            event_type = CallEventType.CALL_RINGING
        elif status == "initiated":
            event_type = CallEventType.CALL_STARTED

        return WebhookEvent(
            event_type=event_type,
            external_call_id=call_id,
            status=status,
            transcript=transcript,
            summary=summary,
            recording_url=recording_url,
            duration_seconds=int(duration) if duration is not None else None,
            raw_data=payload,
        )

    async def cancel_call(self, external_call_id: str) -> bool:
        """End an active Bland call if supported."""
        if not self.api_key:
            return False
        try:
            headers = {"Authorization": self.api_key}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{BASE_URL}/calls/{external_call_id}/end",
                    headers=headers,
                ) as response:
                    return response.status in [200, 204]
        except Exception as e:
            logger.warning("Failed to cancel Bland call %s: %s", external_call_id, e)
            return False
