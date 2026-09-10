"""Consent-gated Conversions API delivery, disabled by default through flags."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import Deal
from app.models.lead import Lead
from app.models.meta import MetaAsset
from app.models.meta_ads import MetaConversionEvent, MetaLeadAttribution
from app.models.property import Property
from app.services.meta.client import MetaGraphClient, MetaGraphError
from app.services.meta.feature_flags import MetaFeatureFlagService
from app.services.meta.resolver import MetaAssetResolver


def _hash(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest() if normalized else None


class MetaConversionsService:
    @staticmethod
    async def send_purchase_for_deal(db: AsyncSession, *, deal_id: int) -> str:
        row = (await db.execute(
            select(Deal, Lead, Property)
            .join(
                Lead,
                and_(Lead.id == Deal.lead_id, Lead.broker_id == Deal.broker_id),
            )
            .join(
                Property,
                and_(Property.id == Deal.property_id, Property.broker_id == Deal.broker_id),
            )
            .where(Deal.id == deal_id)
        )).first()
        if not row:
            return "not_found"
        deal, lead, prop = row
        if deal.stage != "escritura_firmada":
            return "not_purchase"
        flags = await MetaFeatureFlagService.effective(db, deal.broker_id)
        if not flags["channels"].get("conversions_api", False):
            return "disabled"
        consent = (lead.lead_metadata or {}).get("meta_conversion_consent")
        consent_basis = (lead.lead_metadata or {}).get("meta_conversion_consent_basis")
        if consent is not True or not consent_basis:
            return "no_consent"
        attributed = await db.scalar(select(MetaLeadAttribution.id).where(
            MetaLeadAttribution.broker_id == deal.broker_id,
            MetaLeadAttribution.lead_id == lead.id,
            MetaLeadAttribution.source == "meta",
        ).limit(1))
        if attributed is None:
            return "not_attributed"
        dataset = await db.scalar(select(MetaAsset).where(
            MetaAsset.broker_id == deal.broker_id,
            MetaAsset.asset_type == "pixel",
            MetaAsset.owner_type == "broker",
            MetaAsset.approval_status == "approved",
            MetaAsset.status == "active",
            MetaAsset.is_default.is_(True),
        ).limit(1))
        if not dataset or "conversions" not in (dataset.capabilities or []):
            return "dataset_missing"
        event_id = f"deal:{deal.id}:purchase"
        event = await db.scalar(select(MetaConversionEvent).where(
            MetaConversionEvent.broker_id == deal.broker_id,
            MetaConversionEvent.event_id == event_id,
        ))
        if event and event.status == "sent":
            return "duplicate"
        if event is None:
            event = MetaConversionEvent(
                broker_id=deal.broker_id,
                lead_id=lead.id,
                dataset_asset_id=dataset.id,
                event_id=event_id,
                event_name="Purchase",
                consent_basis=str(consent_basis)[:100],
            )
            db.add(event)
            await db.commit()
        resolved = await MetaAssetResolver.by_external_id(
            db,
            asset_type="pixel",
            external_id=dataset.external_id,
            broker_id=deal.broker_id,
            require_capability="conversions",
        )
        price = Decimal(prop.offer_price_clp or prop.list_price_clp or prop.price_clp or 0)
        user_data = {key: value for key, value in {
            "em": [_hash(lead.email)] if lead.email else None,
            "ph": [_hash(lead.phone)] if lead.phone and not lead.phone.startswith("meta_") else None,
        }.items() if value}
        payload = {
            "data": [{
                "event_name": "Purchase",
                "event_time": int((deal.escritura_signed_at or datetime.now(timezone.utc)).timestamp()),
                "event_id": event_id,
                "action_source": "system_generated",
                "user_data": user_data,
                "custom_data": {
                    "currency": "CLP",
                    "value": float(price),
                    "content_ids": [str(prop.id)],
                    "content_type": "product",
                },
            }],
        }
        try:
            response = await MetaGraphClient(access_token=resolved.access_token).post(
                f"/{dataset.external_id}/events",
                json=payload,
            )
            event.status = "sent"
            event.provider_event_id = str(response.get("fbtrace_id") or "") or None
            event.sent_at = datetime.now(timezone.utc)
            event.last_error_code = None
            await db.commit()
            return "sent"
        except MetaGraphError as exc:
            event.status = "failed"
            event.last_error_code = exc.category
            await db.commit()
            raise
