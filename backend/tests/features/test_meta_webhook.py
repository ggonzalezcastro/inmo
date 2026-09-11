"""Verification and signature checks for the unified Meta webhook."""

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.database import get_db
from app.features.meta import webhooks as webhooks_module
from app.services.meta.webhook_inbox import MetaWebhookInboxService


VERIFY_TOKEN = "meta-test-verify"
APP_SECRET = "meta-test-app-secret"
PAYLOAD = {"object": "instagram", "entry": [{"id": "ig-test"}]}


@pytest.fixture
def meta_client(monkeypatch):
    monkeypatch.setattr(settings, "META_WEBHOOK_VERIFY_TOKEN", VERIFY_TOKEN)
    monkeypatch.setattr(settings, "META_APP_SECRET", "parent-meta-app-secret")
    monkeypatch.setattr(settings, "META_INSTAGRAM_APP_SECRET", APP_SECRET)

    async def override_db():
        yield object()

    app = FastAPI()
    app.include_router(webhooks_module.router, prefix="/webhooks/meta")
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client


def _signature(body: bytes) -> str:
    digest = hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_meta_webhook_get_returns_challenge_for_matching_token(meta_client):
    response = meta_client.get(
        "/webhooks/meta",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "challenge-123",
        },
    )

    assert response.status_code == 200
    assert response.text == "challenge-123"
    assert response.headers["content-type"].startswith("text/plain")


def test_meta_webhook_get_rejects_non_matching_token(meta_client):
    response = meta_client.get(
        "/webhooks/meta",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "not-the-token",
            "hub.challenge": "challenge-123",
        },
    )

    assert response.status_code == 403


def test_meta_webhook_post_accepts_valid_signature_and_dispatches(meta_client):
    body = json.dumps(PAYLOAD, separators=(",", ":")).encode()
    event = SimpleNamespace(id=77)
    task = MagicMock()

    with (
        patch.object(
            MetaWebhookInboxService,
            "ingest",
            new=AsyncMock(return_value=(event, False)),
        ) as ingest,
        patch.dict(
            "sys.modules",
            {"app.tasks.meta_tasks": MagicMock(process_meta_webhook_event=task)},
        ),
    ):
        response = meta_client.post(
            "/webhooks/meta",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": _signature(body),
            },
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "duplicate": False}
    assert ingest.await_args.kwargs["raw_body"] == body
    assert ingest.await_args.kwargs["signature_verified"] is True
    task.delay.assert_called_once_with(77)


def test_meta_webhook_post_rejects_invalid_signature_before_ingest(meta_client):
    body = json.dumps(PAYLOAD, separators=(",", ":")).encode()

    with patch.object(
        MetaWebhookInboxService,
        "ingest",
        new=AsyncMock(),
    ) as ingest:
        response = meta_client.post(
            "/webhooks/meta",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid",
            },
        )

    assert response.status_code == 403
    ingest.assert_not_awaited()
