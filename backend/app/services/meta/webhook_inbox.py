"""Secure durable inbox for Meta webhook payloads."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.meta_encryption import encrypt_meta_json
from app.models.meta import MetaAsset, MetaWebhookEvent
from app.services.meta.normalization import (
    NormalizedLeadgen,
    NormalizedMetaMessage,
    NormalizedMetaStatus,
    normalize_meta_payload,
)
from app.services.meta.metrics import record_webhook


def classify_payload(payload: Dict[str, Any]) -> Tuple[str, str, str, str]:
    events = normalize_meta_payload(payload)
    if events:
        first = events[0]
        if isinstance(first, NormalizedMetaMessage):
            return first.provider, "message", first.asset_type, first.asset_external_id
        if isinstance(first, NormalizedMetaStatus):
            return first.provider, "message_status", first.asset_type, first.asset_external_id
        if isinstance(first, NormalizedLeadgen):
            return "leadgen", "leadgen", "facebook_page", first.asset_external_id
    object_type = str(payload.get("object") or "unknown")
    provider = {
        "whatsapp_business_account": "whatsapp",
        "instagram": "instagram",
        "page": "facebook",
    }.get(object_type, "unknown")
    return provider, "unknown", "unknown", ""


class MetaWebhookInboxService:
    @staticmethod
    async def ingest(
        db: AsyncSession,
        *,
        payload: Dict[str, Any],
        raw_body: bytes,
        signature_verified: bool,
    ) -> tuple[MetaWebhookEvent, bool]:
        provider, event_type, asset_type, external_id = classify_payload(payload)
        asset = None
        if external_id and asset_type != "unknown":
            asset = await db.scalar(
                select(MetaAsset).where(
                    MetaAsset.asset_type == asset_type,
                    MetaAsset.external_id == external_id,
                )
            )
        idempotency_key = hashlib.sha256(
            b"meta-webhook-v1:" + provider.encode() + b":" + raw_body
        ).hexdigest()
        existing = await db.scalar(
            select(MetaWebhookEvent).where(
                MetaWebhookEvent.idempotency_key == idempotency_key
            )
        )
        if existing:
            record_webhook(provider, event_type, "duplicate")
            return existing, True

        event = MetaWebhookEvent(
            broker_id=asset.broker_id if asset else None,
            asset_id=asset.id if asset else None,
            provider=provider,
            event_type=event_type,
            idempotency_key=idempotency_key,
            signature_verified=signature_verified,
            payload_ciphertext=encrypt_meta_json(payload),
            payload_expires_at=datetime.now(timezone.utc) + timedelta(
                days=settings.META_RAW_WEBHOOK_RETENTION_DAYS
            ),
            status="pending",
        )
        db.add(event)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            existing = await db.scalar(
                select(MetaWebhookEvent).where(
                    MetaWebhookEvent.idempotency_key == idempotency_key
                )
            )
            if existing:
                record_webhook(provider, event_type, "duplicate")
                return existing, True
            raise
        await db.refresh(event)
        record_webhook(provider, event_type, "accepted")
        return event, False
