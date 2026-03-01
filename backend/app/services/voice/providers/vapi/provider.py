"""
Vapi.ai Voice Provider - implements BaseVoiceProvider.
"""
from typing import Dict, Any, Optional
import logging
from datetime import datetime

import aiohttp

from app.config import settings
from app.services.broker import BrokerVoiceConfigService
from app.services.voice.base_provider import BaseVoiceProvider
from app.services.voice.types import (
    MakeCallRequest,
    CallStatusResult,
    WebhookEvent,
    CallEventType,
    VoiceProviderType,
)

logger = logging.getLogger(__name__)

# Map Vapi string event types to our internal event_type
_VAPI_STATUS_TO_EVENT: Dict[str, CallEventType] = {
    "queued": CallEventType.STATUS_UPDATE,
    "ringing": CallEventType.CALL_RINGING,
    "in-progress": CallEventType.CALL_ANSWERED,
    "ended": CallEventType.CALL_ENDED,
    "failed": CallEventType.CALL_FAILED,
    "busy": CallEventType.CALL_FAILED,
    "no-answer": CallEventType.CALL_FAILED,
}


class VapiProvider(BaseVoiceProvider):
    """Vapi.ai voice agent provider."""

    def __init__(self):
        self.api_key = getattr(settings, "VAPI_API_KEY", None) or None
        self.phone_number_id = getattr(settings, "VAPI_PHONE_NUMBER_ID", None) or None
        self.base_url = "https://api.vapi.ai"
        if not self.api_key:
            logger.warning("Vapi API key not configured")
        else:
            logger.info("Vapi client initialized")

    def get_provider_type(self) -> VoiceProviderType:
        return VoiceProviderType.VAPI

    async def make_call(self, request: MakeCallRequest) -> str:
        """Start outbound call via Vapi. Returns external_call_id."""
        if not self.api_key:
            raise ValueError("Vapi API key not configured")

        metadata = request.metadata or {}
        db = metadata.get("db")
        broker_id = request.broker_id
        agent_type = request.agent_type
        webhook_url = (
            f"{getattr(settings, 'WEBHOOK_BASE_URL', 'http://localhost:8000')}"
            "/api/v1/calls/webhooks/voice"
        )

        phone_number_id = None
        if db is not None and broker_id is not None:
            phone_number_id = await BrokerVoiceConfigService.get_phone_number_id(
                db, broker_id
            )
        if not phone_number_id:
            phone_number_id = self.phone_number_id
        if not phone_number_id:
            raise ValueError(
                "No phone_number_id configured. Set BrokerVoiceConfig.phone_number_id "
                "or VAPI_PHONE_NUMBER_ID in settings."
            )

        assistant_id = None
        if db is not None and broker_id is not None:
            assistant_id = await BrokerVoiceConfigService.get_assistant_id(
                db, broker_id, agent_type
            )
        if not assistant_id:
            assistant_id = getattr(settings, "VAPI_ASSISTANT_ID", None) or None
        if not assistant_id:
            raise ValueError(
                "No assistant_id configured. Set BrokerVoiceConfig.assistant_id_default "
                "or VAPI_ASSISTANT_ID in settings."
            )

        payload = {
            "assistantId": assistant_id,
            "phoneNumberId": phone_number_id,
            "customer": {
                "number": request.phone_number,
                "numberE164CheckEnabled": True,
            },
            "assistantOverrides": {
                "server": {
                    "url": webhook_url,
                },
            },
            "metadata": {
                "lead_id": request.lead_id,
                "campaign_id": metadata.get("campaign_id"),
                "broker_id": broker_id,
                "assistant_type": agent_type or "default",
            },
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/call",
                json=payload,
                headers=headers,
            ) as response:
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    logger.error("Vapi API error: %s - %s", response.status, error_text)
                    raise ValueError(f"Failed to create call: {error_text}")

                result = await response.json()
                call_id = result.get("id")
                logger.info("Vapi call initiated: %s to %s", call_id, request.phone_number)
                return call_id

    async def get_call_status(self, external_call_id: str) -> CallStatusResult:
        """Get call status from Vapi."""
        if not self.api_key:
            raise ValueError("Vapi API key not configured")

        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/call/{external_call_id}",
                headers=headers,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"Failed to get call status: {error_text}")

                call_data = await response.json()
                duration = None
                if call_data.get("endedAt") and call_data.get("startedAt"):
                    duration = self._calculate_duration(call_data)

                return CallStatusResult(
                    external_call_id=call_data.get("id", external_call_id),
                    status=call_data.get("status", "unknown"),
                    duration_seconds=duration,
                    transcript=call_data.get("transcript"),
                    recording_url=call_data.get("recordingUrl"),
                )

    async def handle_webhook(self, payload: dict, headers: dict = None) -> WebhookEvent:
        """Parse Vapi webhook and return normalized WebhookEvent."""
        message = payload.get("message", {})
        message_type = message.get("type")
        call = message.get("call", {})
        call_id = call.get("id") or ""

        event_type = CallEventType.STATUS_UPDATE
        status = call.get("status")
        transcript = call.get("transcript")
        summary = call.get("summary")
        duration_seconds = self._calculate_duration(call)
        recording_url = call.get("recordingUrl")
        ended_reason = None
        artifact_messages = None
        tool_calls_data = None
        call_id_from_metadata = (call.get("metadata") or {}).get("call_id")
        vapi_metadata = call.get("metadata") or {}
        if not vapi_metadata:
            vapi_metadata = message.get("metadata") or {}
        broker_id_raw = vapi_metadata.get("broker_id")
        assistant_type_from_meta = vapi_metadata.get("assistant_type")

        if message_type == "status-update":
            status = message.get("status") or status
            event_type = _VAPI_STATUS_TO_EVENT.get(
                status, CallEventType.STATUS_UPDATE
            )
        elif message_type == "call-started":
            event_type = CallEventType.CALL_STARTED
        elif message_type == "transcript":
            event_type = CallEventType.TRANSCRIPT_UPDATE
            transcript = message.get("transcript") or transcript
        elif message_type == "tool-calls":
            event_type = CallEventType.TOOL_CALLS
            tool_with_list = message.get("toolWithToolCallList") or []
            tool_list = message.get("toolCallList") or []
            if tool_with_list:
                tool_calls_data = [
                    {
                        "name": item.get("name"),
                        "toolCall": item.get("toolCall") or {},
                        "tool_call_id": (item.get("toolCall") or {}).get("id"),
                        "parameters": (item.get("toolCall") or {}).get("parameters") or {},
                    }
                    for item in tool_with_list
                ]
            elif tool_list:
                tool_calls_data = [
                    {
                        "name": item.get("name"),
                        "toolCall": item,
                        "tool_call_id": item.get("id"),
                        "parameters": item.get("parameters") or {},
                    }
                    for item in tool_list
                ]
            else:
                tool_calls_data = []
        elif message_type == "end-of-call-report":
            event_type = CallEventType.END_OF_CALL_REPORT
            artifact = message.get("artifact") or {}
            transcript = artifact.get("transcript") or transcript
            artifact_messages = artifact.get("messages") or []
            recording_obj = artifact.get("recording") or {}
            recording_url = recording_obj.get("url") or recording_url
            ended_reason = message.get("endedReason")
            summary = (artifact.get("summary") or summary) if isinstance(artifact.get("summary"), str) else summary
        elif message_type == "assistant-request":
            event_type = CallEventType.ASSISTANT_REQUEST
        elif message_type == "hang":
            event_type = CallEventType.HANG

        return WebhookEvent(
            event_type=event_type,
            external_call_id=call_id,
            status=status,
            transcript=transcript,
            summary=summary,
            recording_url=recording_url,
            duration_seconds=duration_seconds,
            raw_data=payload,
            ended_reason=ended_reason,
            artifact_messages=artifact_messages,
            tool_calls_data=tool_calls_data,
            call_id_from_metadata=call_id_from_metadata,
            broker_id=int(broker_id_raw) if broker_id_raw else None,
            assistant_type=assistant_type_from_meta,
        )

    async def cancel_call(self, external_call_id: str) -> bool:
        """Cancel an active Vapi call."""
        if not self.api_key:
            return False
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/call/{external_call_id}/end",
                    headers=headers,
                ) as response:
                    return response.status in [200, 204]
        except Exception as e:
            logger.warning("Failed to cancel Vapi call %s: %s", external_call_id, e)
            return False

    def _calculate_duration(self, call: Dict[str, Any]) -> Optional[int]:
        started_at = call.get("startedAt")
        ended_at = call.get("endedAt")
        if not started_at or not ended_at:
            return None
        try:
            start = datetime.fromisoformat(
                started_at.replace("Z", "+00:00")
            )
            end = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
            return int((end - start).total_seconds())
        except Exception as e:
            logger.warning("Error calculating duration: %s", e)
            return None
