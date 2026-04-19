"""
Tests for voice provider abstraction: types, factory, webhook normalization.
Run with: pytest tests/services/test_voice_providers.py -v
"""
import pytest
pytestmark = pytest.mark.asyncio

from app.services.voice.types import (
    VoiceProviderType,
    CallEventType,
    WebhookEvent,
    CallStatusResult,
    MakeCallRequest,
)
from app.services.voice.base_provider import BaseVoiceProvider
from app.services.voice.factory import get_voice_provider, register_voice_provider
from app.services.voice.providers.vapi.provider import VapiProvider
from app.services.voice.providers.bland.provider import BlandProvider
from app.services.voice.call_service import _webhook_event_to_legacy


class TestVoiceTypes:
    def test_voice_provider_type_values(self):
        assert VoiceProviderType.VAPI.value == "vapi"
        assert VoiceProviderType.BLAND.value == "bland"

    def test_webhook_event_dataclass(self):
        ev = WebhookEvent(
            event_type=CallEventType.CALL_ENDED,
            external_call_id="call-123",
            status="ended",
            transcript="Hello",
            duration_seconds=120,
        )
        assert ev.external_call_id == "call-123"
        assert ev.event_type == CallEventType.CALL_ENDED
        assert ev.duration_seconds == 120

    def test_make_call_request(self):
        req = MakeCallRequest(phone_number="+56912345678", broker_id=1)
        assert req.phone_number == "+56912345678"
        assert req.broker_id == 1
        assert req.lead_id is None


class TestFactory:
    @pytest.mark.asyncio
    async def test_get_voice_provider_default_returns_vapi(self):
        provider = await get_voice_provider()
        assert isinstance(provider, VapiProvider)

    @pytest.mark.asyncio
    async def test_get_voice_provider_by_type_vapi(self):
        provider = await get_voice_provider(provider_type="vapi")
        assert isinstance(provider, VapiProvider)

    @pytest.mark.asyncio
    async def test_get_voice_provider_by_type_bland(self):
        provider = await get_voice_provider(provider_type="bland")
        assert isinstance(provider, BlandProvider)

    @pytest.mark.asyncio
    async def test_get_voice_provider_unknown_falls_back_to_vapi(self):
        provider = await get_voice_provider(provider_type="unknown")
        assert isinstance(provider, VapiProvider)


class TestVapiWebhookNormalization:
    @pytest.mark.asyncio
    async def test_vapi_status_update_maps_to_webhook_event(self):
        provider = VapiProvider()
        payload = {
            "message": {
                "type": "status-update",
                "status": "ended",
                "call": {
                    "id": "vapi-call-1",
                    "status": "ended",
                    "startedAt": "2025-02-21T10:00:00Z",
                    "endedAt": "2025-02-21T10:02:00Z",
                    "recordingUrl": "https://example.com/rec",
                    "transcript": "Full transcript",
                    "summary": "Call summary",
                },
            },
        }
        event = await provider.handle_webhook(payload)
        assert event.external_call_id == "vapi-call-1"
        assert event.event_type == CallEventType.CALL_ENDED
        assert event.transcript == "Full transcript"
        assert event.summary == "Call summary"
        assert event.recording_url == "https://example.com/rec"

    @pytest.mark.asyncio
    async def test_vapi_transcript_update_maps_to_transcript_event(self):
        provider = VapiProvider()
        payload = {
            "message": {
                "type": "transcript",
                "transcript": "Partial line",
                "call": {"id": "vapi-call-2"},
            },
        }
        event = await provider.handle_webhook(payload)
        assert event.event_type == CallEventType.TRANSCRIPT_UPDATE
        assert event.external_call_id == "vapi-call-2"


class TestBlandWebhookNormalization:
    @pytest.mark.asyncio
    async def test_bland_completed_payload_maps_to_webhook_event(self):
        provider = BlandProvider()
        payload = {
            "call_id": "bland-call-1",
            "status": "completed",
            "transcript": "Bland transcript",
            "call_length": 90,
            "recording_url": "https://bland.com/rec",
        }
        event = await provider.handle_webhook(payload)
        assert event.external_call_id == "bland-call-1"
        assert event.event_type == CallEventType.CALL_ENDED
        assert event.transcript == "Bland transcript"
        assert event.duration_seconds == 90


class TestWebhookEventToLegacy:
    def test_call_ended_maps_to_completed(self):
        ev = WebhookEvent(
            event_type=CallEventType.CALL_ENDED,
            external_call_id="x",
            status="ended",
        )
        event_str, meta = _webhook_event_to_legacy(ev)
        assert event_str == "completed"

    def test_transcript_update_maps_to_transcript(self):
        ev = WebhookEvent(
            event_type=CallEventType.TRANSCRIPT_UPDATE,
            external_call_id="x",
        )
        event_str, meta = _webhook_event_to_legacy(ev)
        assert event_str == "transcript"
        assert "message_data" in meta
