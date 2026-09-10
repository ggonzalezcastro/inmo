"""Contract tests for signed Meta webhooks and cross-channel normalization."""

from __future__ import annotations

import hashlib
import hmac
import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.features.meta.webhooks import _decode_signed_request, verify_meta_signature
from app.schemas.meta_inbox import MetaInboxSendRequest
from app.services.chat.instagram_provider import InstagramProvider
from app.services.chat.messenger_provider import MessengerProvider
from app.services.chat.whatsapp_provider import WhatsAppProvider
from app.services.meta.normalization import (
    NormalizedLeadgen,
    NormalizedMetaMessage,
    NormalizedMetaStatus,
    normalize_meta_payload,
)
from app.services.meta.inbound import _auto_send_block_reason


def test_whatsapp_normalizes_every_message_media_and_status():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{"value": {
                "metadata": {"phone_number_id": "phone-1"},
                "contacts": [{"wa_id": "56911111111", "profile": {"name": "Ana"}}],
                "messages": [
                    {
                        "from": "56911111111",
                        "id": "wamid.1",
                        "type": "text",
                        "text": {"body": "Hola"},
                    },
                    {
                        "from": "56911111111",
                        "id": "wamid.2",
                        "type": "image",
                        "image": {"id": "media-1", "mime_type": "image/jpeg", "caption": "Plano"},
                    },
                ],
                "statuses": [{"id": "wamid.out", "status": "delivered"}],
            }}],
        }],
    }
    events = normalize_meta_payload(payload)
    assert len(events) == 3
    assert isinstance(events[0], NormalizedMetaMessage)
    assert events[0].username == "Ana"
    assert events[0].asset_external_id == "phone-1"
    assert events[1].attachments[0]["id"] == "media-1"
    assert isinstance(events[2], NormalizedMetaStatus)
    assert events[2].status == "delivered"


@pytest.mark.parametrize(
    ("object_type", "provider", "asset_type"),
    [
        ("instagram", "instagram", "instagram_account"),
        ("page", "facebook", "facebook_page"),
    ],
)
def test_instagram_and_messenger_identity_is_scoped_to_recipient_asset(
    object_type,
    provider,
    asset_type,
):
    payload = {
        "object": object_type,
        "entry": [{
            "id": "asset-1",
            "messaging": [{
                "sender": {"id": "person-1"},
                "recipient": {"id": "asset-1"},
                "message": {"mid": "mid.1", "text": "¿Tienen departamentos?"},
            }],
        }],
    }
    events = normalize_meta_payload(payload)
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, NormalizedMetaMessage)
    assert event.provider == provider
    assert event.asset_type == asset_type
    assert event.asset_external_id == "asset-1"
    assert event.sender_id == "person-1"


def test_page_leadgen_is_preserved_as_distinct_event():
    events = normalize_meta_payload({
        "object": "page",
        "entry": [{
            "id": "page-1",
            "changes": [{
                "field": "leadgen",
                "value": {
                    "page_id": "page-1",
                    "leadgen_id": "leadgen-1",
                    "form_id": "form-1",
                    "ad_id": "ad-1",
                },
            }],
        }],
    })
    assert len(events) == 1
    assert isinstance(events[0], NormalizedLeadgen)
    assert events[0].leadgen_id == "leadgen-1"
    assert events[0].ad_id == "ad-1"


def test_messenger_delivery_and_read_receipts_are_normalized():
    events = normalize_meta_payload({
        "object": "page",
        "entry": [{
            "id": "page-1",
            "messaging": [
                {"sender": {"id": "person-1"}, "recipient": {"id": "page-1"}, "delivery": {"mids": ["mid.out"], "watermark": 1700000000000}},
                {"sender": {"id": "person-1"}, "recipient": {"id": "page-1"}, "read": {"watermark": 1700000001000}},
            ],
        }],
    })
    assert [event.status for event in events] == ["delivered", "read"]
    assert events[0].message_id == "mid.out"
    assert events[1].metadata["sender_id"] == "person-1"


def test_signature_is_computed_over_original_body(monkeypatch):
    secret = "meta-app-secret"
    raw = b'{"entry":[{"id":"1"}]}'
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    monkeypatch.setattr(settings, "META_APP_SECRET", secret)
    assert verify_meta_signature(raw, f"sha256={signature}") is True
    assert verify_meta_signature(raw, signature) is False
    assert verify_meta_signature(raw + b" ", f"sha256={signature}") is False


def test_signature_fails_closed_in_production_without_secret(monkeypatch):
    monkeypatch.setattr(settings, "META_APP_SECRET", "")
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_SECRET", "")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    assert verify_meta_signature(b'{"entry":[]}', "") is False


def test_data_deletion_signed_request_rejects_tampering(monkeypatch):
    secret = "meta-app-secret"
    monkeypatch.setattr(settings, "META_APP_SECRET", secret)
    payload = base64.urlsafe_b64encode(json.dumps({
        "algorithm": "HMAC-SHA256",
        "user_id": "meta-user-1",
    }).encode()).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(
        hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")
    assert _decode_signed_request(f"{signature}.{payload}")["user_id"] == "meta-user-1"
    with pytest.raises(HTTPException):
        _decode_signed_request(f"{signature}.{payload}x")


def test_meta_inbox_media_contract_requires_https_and_type():
    request = MetaInboxSendRequest(
        text="Plano del proyecto",
        media_url="https://cdn.example.com/plano.pdf",
        media_type="document",
    )
    assert request.media_type == "document"
    with pytest.raises(ValidationError):
        MetaInboxSendRequest(text="", media_url="https://cdn.example.com/plano.pdf")
    with pytest.raises(ValidationError):
        MetaInboxSendRequest(text="", media_url="http://cdn.example.com/plano.pdf", media_type="document")


def test_supervised_auto_blocks_low_confidence_and_financial_promises():
    event = NormalizedMetaMessage(
        provider="instagram",
        asset_type="instagram_account",
        asset_external_id="ig-1",
        sender_id="person-1",
        message_id="mid-1",
        text="¿Puedo comprar?",
    )
    assert _auto_send_block_reason(event, SimpleNamespace(response="Te aprobarán seguro", metadata={"confidence": 0.4})) == "low_confidence"
    assert _auto_send_block_reason(event, SimpleNamespace(response="Tienes crédito garantizado", metadata={})) == "unsafe_financial_claim"
    assert _auto_send_block_reason(event, SimpleNamespace(response="Podemos revisar tus antecedentes.", metadata={})) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "expected_path"),
    [
        (WhatsAppProvider({"phone_number_id": "phone-1", "access_token": "token"}), "phone-1/messages"),
        (InstagramProvider({"asset_id": "ig-1", "access_token": "token"}), "ig-1/messages"),
        (MessengerProvider({"asset_id": "page-1", "access_token": "token"}), "page-1/messages"),
    ],
)
async def test_meta_providers_send_through_their_exact_asset(provider, expected_path):
    provider.client.post = AsyncMock(return_value={"message_id": "mid.out", "messages": [{"id": "wamid.out"}]})
    result = await provider.send_message("person-1", "Hola")
    assert result.success is True
    assert provider.client.post.await_args.args[0] == expected_path


@pytest.mark.asyncio
async def test_whatsapp_template_payload_is_used_when_requested():
    provider = WhatsAppProvider({"phone_number_id": "phone-1", "access_token": "token"})
    provider.client.post = AsyncMock(return_value={"messages": [{"id": "wamid.template"}]})
    result = await provider.send_message(
        "56911111111",
        "",
        template_name="seguimiento_24h",
        template_language="es_CL",
    )
    assert result.success is True
    payload = provider.client.post.await_args.kwargs["json"]
    assert payload["type"] == "template"
    assert payload["template"]["name"] == "seguimiento_24h"
