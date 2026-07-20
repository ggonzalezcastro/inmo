"""
Tests for X-Twilio-Signature validation on Pipecat webhooks (audit H1).

Run standalone (no DB):
    .venv/bin/python -m pytest tests/routes/test_twilio_signature.py -v --noconftest
"""
import pytest
from fastapi import HTTPException
from twilio.request_validator import RequestValidator

from app.core.config import settings
from app.routes.voice import _verify_twilio_request

AUTH_TOKEN = "test_auth_token_12345"
BASE_URL = "http://localhost:8000"
PATH = "/api/v1/calls/pipecat/twiml/inbound"
FORM = {"From": "+56911111111", "To": "+56222222222", "CallSid": "CA123"}


class _FakeURL:
    def __init__(self, path: str, query: str = ""):
        self.path = path
        self.query = query


class _FakeRequest:
    def __init__(self, form: dict, signature: str = "", path: str = PATH):
        self._form = form
        self.headers = {"X-Twilio-Signature": signature} if signature else {}
        self.url = _FakeURL(path)

    async def form(self):
        return self._form


def _valid_signature() -> str:
    return RequestValidator(AUTH_TOKEN).compute_signature(BASE_URL + PATH, FORM)


@pytest.fixture(autouse=True)
def _twilio_settings(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", AUTH_TOKEN)
    monkeypatch.setattr(settings, "WEBHOOK_BASE_URL", BASE_URL)


async def test_missing_signature_rejected():
    with pytest.raises(HTTPException) as exc:
        await _verify_twilio_request(_FakeRequest(FORM))
    assert exc.value.status_code == 403


async def test_invalid_signature_rejected():
    with pytest.raises(HTTPException) as exc:
        await _verify_twilio_request(_FakeRequest(FORM, signature="bogus=="))
    assert exc.value.status_code == 403


async def test_valid_signature_accepted():
    form = await _verify_twilio_request(_FakeRequest(FORM, signature=_valid_signature()))
    assert form == FORM


async def test_tampered_form_rejected():
    tampered = {**FORM, "From": "+56999999999"}
    with pytest.raises(HTTPException) as exc:
        await _verify_twilio_request(_FakeRequest(tampered, signature=_valid_signature()))
    assert exc.value.status_code == 403


async def test_missing_auth_token_rejects_all(monkeypatch):
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "")
    with pytest.raises(HTTPException) as exc:
        await _verify_twilio_request(_FakeRequest(FORM, signature=_valid_signature()))
    assert exc.value.status_code == 403
