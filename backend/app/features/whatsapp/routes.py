"""
WhatsApp Business API webhook endpoints.

Meta requires a single, broker-agnostic URL for webhook verification and
inbound message delivery. This router is mounted at /webhooks/whatsapp.
"""
import hashlib
import hmac
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def whatsapp_verify(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification (hub challenge handshake)."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def whatsapp_webhook(request: Request):
    """
    Receive inbound WhatsApp messages from Meta.

    Always returns 200 {"status": "ok"} — Meta retries on any non-2xx response,
    so we must never surface errors to the caller.
    """
    body = await request.body()

    # Validate HMAC-SHA256 signature
    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, signature_header):
        logger.warning("WhatsApp webhook: invalid signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(body)
        from_number, message_text, wamid, phone_number_id = _extract_message(payload)
        if from_number and message_text:
            from app.tasks.whatsapp_tasks import process_whatsapp_message  # lazy import
            process_whatsapp_message.delay(
                from_number=from_number,
                message_text=message_text,
                wamid=wamid,
                phone_number_id=phone_number_id,
            )
        else:
            logger.debug("WhatsApp webhook: no actionable message in payload")
    except Exception:
        logger.exception("WhatsApp webhook: error processing payload")

    return {"status": "ok"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _verify_signature(body: bytes, signature_header: str) -> bool:
    """Return True when HMAC-SHA256(secret, body) matches the header value."""
    secret = settings.WHATSAPP_WEBHOOK_SECRET
    if not secret:
        logger.warning("WHATSAPP_WEBHOOK_SECRET not set — skipping signature check")
        return True

    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    received = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


def _extract_message(payload: dict) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Extract (from_number, message_text, wamid, phone_number_id) from a
    WhatsApp Cloud API webhook payload.
    Returns (None, None, None, None) for non-message events (e.g. read receipts).
    """
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return None, None, None, None

        msg = messages[0]
        msg_type = msg.get("type", "")
        message_text: Optional[str] = None

        if msg_type == "text":
            message_text = msg.get("text", {}).get("body")
        elif msg_type == "button":
            message_text = msg.get("button", {}).get("text")
        elif msg_type == "interactive":
            interactive = msg.get("interactive", {})
            if interactive.get("type") == "button_reply":
                message_text = interactive.get("button_reply", {}).get("title")
            elif interactive.get("type") == "list_reply":
                message_text = interactive.get("list_reply", {}).get("title")

        if not message_text:
            return None, None, None, None

        from_number = msg.get("from")
        wamid = msg.get("id")
        phone_number_id = value.get("metadata", {}).get("phone_number_id")
        return from_number, message_text, wamid, phone_number_id
    except Exception:
        logger.exception("WhatsApp webhook: error extracting message")
        return None, None, None, None
