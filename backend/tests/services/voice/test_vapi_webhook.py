"""
Tests for VAPI webhook parsing in provider.handle_webhook.
Run with: pytest tests/services/voice/test_vapi_webhook.py -v
"""
import pytest

pytestmark = pytest.mark.asyncio

from app.services.voice.types import CallEventType
from app.services.voice.providers.vapi.provider import VapiProvider


async def test_status_update_ended():
    """status-update with status=ended maps to CallEventType.CALL_ENDED."""
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


async def test_end_of_call_report():
    """end-of-call-report with artifact data extracts transcript, messages, recording_url, ended_reason."""
    provider = VapiProvider()
    payload = {
        "message": {
            "type": "end-of-call-report",
            "call": {"id": "vapi-call-2"},
            "endedReason": "customer-ended-call",
            "artifact": {
                "transcript": "Agent: Hola. Customer: Hola, quiero información.",
                "messages": [
                    {"role": "assistant", "content": "Hola."},
                    {"role": "user", "content": "Hola, quiero información."},
                ],
                "recording": {"url": "https://vapi.rec/abc123"},
            },
        },
    }
    event = await provider.handle_webhook(payload)
    assert event.event_type == CallEventType.END_OF_CALL_REPORT
    assert event.external_call_id == "vapi-call-2"
    assert event.transcript == "Agent: Hola. Customer: Hola, quiero información."
    assert event.artifact_messages == [
        {"role": "assistant", "content": "Hola."},
        {"role": "user", "content": "Hola, quiero información."},
    ]
    assert event.recording_url == "https://vapi.rec/abc123"
    assert event.ended_reason == "customer-ended-call"


async def test_tool_calls_event():
    """tool-calls with toolWithToolCallList extracts tool_calls_data correctly."""
    provider = VapiProvider()
    payload = {
        "message": {
            "type": "tool-calls",
            "call": {"id": "vapi-call-3"},
            "toolWithToolCallList": [
                {
                    "name": "get_weather",
                    "toolCall": {
                        "id": "tc-1",
                        "parameters": {"city": "Santiago"},
                    },
                },
                {
                    "name": "schedule_visit",
                    "toolCall": {
                        "id": "tc-2",
                        "parameters": {"date": "2025-03-01"},
                    },
                },
            ],
        },
    }
    event = await provider.handle_webhook(payload)
    assert event.event_type == CallEventType.TOOL_CALLS
    assert event.external_call_id == "vapi-call-3"
    assert event.tool_calls_data is not None
    assert len(event.tool_calls_data) == 2
    assert event.tool_calls_data[0]["name"] == "get_weather"
    assert event.tool_calls_data[0]["tool_call_id"] == "tc-1"
    assert event.tool_calls_data[0]["parameters"] == {"city": "Santiago"}
    assert event.tool_calls_data[1]["name"] == "schedule_visit"
    assert event.tool_calls_data[1]["tool_call_id"] == "tc-2"
    assert event.tool_calls_data[1]["parameters"] == {"date": "2025-03-01"}


async def test_tool_calls_event_tool_call_list_fallback():
    """tool-calls with toolCallList (flatter format) is parsed."""
    provider = VapiProvider()
    payload = {
        "message": {
            "type": "tool-calls",
            "call": {"id": "vapi-call-4"},
            "toolCallList": [
                {"name": "lookup_lead", "id": "tc-a", "parameters": {"phone": "+569"}},
            ],
        },
    }
    event = await provider.handle_webhook(payload)
    assert event.event_type == CallEventType.TOOL_CALLS
    assert len(event.tool_calls_data) == 1
    assert event.tool_calls_data[0]["name"] == "lookup_lead"
    assert event.tool_calls_data[0]["tool_call_id"] == "tc-a"
    assert event.tool_calls_data[0]["parameters"] == {"phone": "+569"}


async def test_assistant_request_event():
    """assistant-request maps to CallEventType.ASSISTANT_REQUEST."""
    provider = VapiProvider()
    payload = {
        "message": {
            "type": "assistant-request",
            "call": {
                "id": "vapi-call-5",
                "phoneNumberId": "vapi-phone-123",
            },
        },
    }
    event = await provider.handle_webhook(payload)
    assert event.event_type == CallEventType.ASSISTANT_REQUEST
    assert event.external_call_id == "vapi-call-5"


async def test_hang_event():
    """hang maps to CallEventType.HANG."""
    provider = VapiProvider()
    payload = {
        "message": {
            "type": "hang",
            "call": {"id": "vapi-call-6"},
        },
    }
    event = await provider.handle_webhook(payload)
    assert event.event_type == CallEventType.HANG
    assert event.external_call_id == "vapi-call-6"


async def test_unknown_event_type():
    """Unknown message type leaves event_type as STATUS_UPDATE (default)."""
    provider = VapiProvider()
    payload = {
        "message": {
            "type": "unknown-event",
            "call": {"id": "vapi-call-7"},
        },
    }
    event = await provider.handle_webhook(payload)
    assert event.external_call_id == "vapi-call-7"
    assert event.event_type == CallEventType.STATUS_UPDATE
