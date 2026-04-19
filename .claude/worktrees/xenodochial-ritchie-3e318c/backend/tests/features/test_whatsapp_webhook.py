"""
Unit tests for the WhatsApp webhook endpoints.

Run without the DB-requiring conftest:
    .venv/bin/python -m pytest tests/features/test_whatsapp_webhook.py -v --noconftest
"""
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ── Minimal app fixture ────────────────────────────────────────────────────────
# We build a throwaway FastAPI app that only mounts the WhatsApp router so that
# we never touch the DB or Celery during these unit tests.

VERIFY_TOKEN = "test-verify-token"
WEBHOOK_SECRET = "test-webhook-secret"

# Minimal WhatsApp webhook payload (single text message)
_SAMPLE_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "broker_id",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "987654321"},
                        "messages": [
                            {
                                "from": "5491112345678",
                                "id": "wamid.abc123",
                                "timestamp": "1700000000",
                                "type": "text",
                                "text": {"body": "Hola, quiero info"},
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}


def _make_signature(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.fixture(scope="module")
def client():
    """TestClient wired to a minimal FastAPI app with the WhatsApp router."""
    with (
        patch("app.core.config.Settings.WHATSAPP_VERIFY_TOKEN", VERIFY_TOKEN, create=True),
        patch("app.core.config.Settings.WHATSAPP_WEBHOOK_SECRET", WEBHOOK_SECRET, create=True),
        patch("app.config.settings") as mock_settings,
    ):
        mock_settings.WHATSAPP_VERIFY_TOKEN = VERIFY_TOKEN
        mock_settings.WHATSAPP_WEBHOOK_SECRET = WEBHOOK_SECRET
        mock_settings.WHATSAPP_ACCESS_TOKEN = "fake-token"
        mock_settings.WHATSAPP_PHONE_NUMBER_ID = "123456789"

        from app.features.whatsapp.routes import router

        app = FastAPI()
        app.include_router(router, prefix="/webhooks/whatsapp")
        yield TestClient(app)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestWhatsAppVerification:
    def test_verification_success(self, client):
        """GET with valid verify_token and challenge → 200, plain-text challenge."""
        response = client.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": VERIFY_TOKEN,
                "hub.challenge": "abc123",
            },
        )
        assert response.status_code == 200
        assert response.text == "abc123"

    def test_verification_invalid_token(self, client):
        """GET with wrong verify_token → 403."""
        response = client.get(
            "/webhooks/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "abc123",
            },
        )
        assert response.status_code == 403


class TestWhatsAppWebhookPost:
    def test_valid_post_signature_dispatches_task(self, client):
        """POST with correct HMAC → 200 {"status": "ok"}, task dispatched."""
        body = json.dumps(_SAMPLE_PAYLOAD).encode()
        sig = _make_signature(body)

        # The task is lazily imported inside the route handler, so we patch the
        # module it lives in directly.
        mock_task = MagicMock()
        mock_delay = MagicMock()
        mock_task.delay = mock_delay

        with patch.dict(
            "sys.modules",
            {"app.tasks.whatsapp_tasks": MagicMock(process_whatsapp_message=mock_task)},
        ):
            response = client.post(
                "/webhooks/whatsapp",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": sig,
                },
            )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_delay.assert_called_once_with(
            from_number="5491112345678",
            message_text="Hola, quiero info",
            wamid="wamid.abc123",
            phone_number_id="987654321",
        )

    def test_invalid_post_signature_returns_403(self, client):
        """POST with wrong HMAC signature → 403."""
        body = json.dumps(_SAMPLE_PAYLOAD).encode()

        response = client.post(
            "/webhooks/whatsapp",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=badhash",
            },
        )
        assert response.status_code == 403

    def test_non_message_payload_returns_ok(self, client):
        """POST with a status-update (read receipt) payload → 200, no task dispatched."""
        # A delivery/read-receipt event has no "messages" key
        read_receipt = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "statuses": [{"id": "wamid.xyz", "status": "read"}],
                            }
                        }
                    ]
                }
            ],
        }
        body = json.dumps(read_receipt).encode()
        sig = _make_signature(body)

        mock_task = MagicMock()
        mock_delay = MagicMock()
        mock_task.delay = mock_delay

        with patch.dict(
            "sys.modules",
            {"app.tasks.whatsapp_tasks": MagicMock(process_whatsapp_message=mock_task)},
        ):
            response = client.post(
                "/webhooks/whatsapp",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": sig,
                },
            )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_delay.assert_not_called()
