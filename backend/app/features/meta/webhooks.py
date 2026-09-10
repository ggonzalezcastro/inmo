"""Global signed webhook endpoint for all Meta business products."""

from __future__ import annotations

import hashlib
import hmac
import json
import base64
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.meta import MetaAsset, MetaConnection, MetaCredential
from app.services.meta.webhook_inbox import MetaWebhookInboxService

router = APIRouter()


def _decode_signed_request(signed_request: str) -> dict:
    secret = settings.META_APP_SECRET
    if not secret or "." not in signed_request:
        raise HTTPException(status_code=403, detail="Invalid signed request")
    encoded_signature, encoded_payload = signed_request.split(".", 1)
    try:
        signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        raw_payload = base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        expected = hmac.new(secret.encode(), encoded_payload.encode(), hashlib.sha256).digest()
        payload = json.loads(raw_payload)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=403, detail="Invalid signed request") from exc
    if not hmac.compare_digest(signature, expected) or payload.get("algorithm") != "HMAC-SHA256":
        raise HTTPException(status_code=403, detail="Invalid signed request")
    return payload


def _confirmation_code(external_user_id: str) -> str:
    digest = hmac.new(
        settings.META_APP_SECRET.encode(),
        f"meta-deletion:{external_user_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def verify_meta_signature(raw_body: bytes, signature_header: str) -> bool:
    secret = settings.META_APP_SECRET or settings.WHATSAPP_WEBHOOK_SECRET
    if not secret:
        return settings.ENVIRONMENT != "production"
    if not signature_header.startswith("sha256="):
        return False
    received = signature_header.removeprefix("sha256=").strip()
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return bool(received) and hmac.compare_digest(expected, received)


@router.get("")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    expected = settings.META_WEBHOOK_VERIFY_TOKEN
    if hub_mode == "subscribe" and expected and hub_verify_token == expected:
        return PlainTextResponse(hub_challenge or "")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def receive_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_meta_signature(raw_body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    event, duplicate = await MetaWebhookInboxService.ingest(
        db,
        payload=payload,
        raw_body=raw_body,
        signature_verified=True,
    )
    if not duplicate:
        from app.tasks.meta_tasks import process_meta_webhook_event
        process_meta_webhook_event.delay(event.id)
    return {"status": "ok", "duplicate": duplicate}


@router.post("/deauthorize")
async def deauthorize_meta_user(
    signed_request: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    payload = _decode_signed_request(signed_request)
    external_user_id = str(payload.get("user_id") or "").strip()
    if not external_user_id:
        raise HTTPException(status_code=422, detail="Missing Meta user")
    connections = list((await db.scalars(
        select(MetaConnection).where(MetaConnection.external_principal_id == external_user_id)
    )).all())
    for connection in connections:
        connection.status = "revoked"
        connection.last_error_code = "USER_DEAUTHORIZED"
        await db.execute(
            update(MetaAsset)
            .where(MetaAsset.connection_id == connection.id)
            .values(status="paused", is_default=False)
        )
        await db.execute(
            update(MetaCredential)
            .where(MetaCredential.connection_id == connection.id)
            .values(status="revoked")
        )
        db.add(AuditLog(
            user_id=None,
            broker_id=connection.broker_id,
            action="meta_user_deauthorized",
            resource_type="meta_connection",
            resource_id=connection.id,
            changes={"status": "revoked"},
        ))
    await db.commit()
    return {"success": True}


@router.post("/data-deletion")
async def delete_meta_user_data(
    signed_request: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    payload = _decode_signed_request(signed_request)
    external_user_id = str(payload.get("user_id") or "").strip()
    if not external_user_id:
        raise HTTPException(status_code=422, detail="Missing Meta user")
    connections = list((await db.scalars(
        select(MetaConnection).where(MetaConnection.external_principal_id == external_user_id)
    )).all())
    for connection in connections:
        broker_id = connection.broker_id
        connection_id = connection.id
        await db.delete(connection)
        db.add(AuditLog(
            user_id=None,
            broker_id=broker_id,
            action="meta_data_deleted",
            resource_type="meta_connection",
            resource_id=connection_id,
            changes={"source": "meta_signed_request"},
        ))
    await db.commit()
    code = _confirmation_code(external_user_id)
    return {
        "url": f"{settings.FRONTEND_URL.rstrip('/')}/data-deletion?code={code}",
        "confirmation_code": code,
    }
