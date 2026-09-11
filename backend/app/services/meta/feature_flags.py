"""Effective global plus per-broker rollout switches for Meta products."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.broker import Broker
from app.models.user import UserRole


FEATURE_KEYS = (
    "whatsapp",
    "instagram",
    "messenger",
    "ads",
    "lead_ads",
    "conversions_api",
)


def _global_switches() -> dict[str, bool]:
    return {
        "whatsapp": settings.META_WHATSAPP_ASSET_ROUTING_ENABLED,
        "instagram": settings.META_INSTAGRAM_ENABLED,
        "messenger": settings.META_MESSENGER_ENABLED,
        "ads": settings.META_ADS_ENABLED,
        "lead_ads": settings.META_LEAD_ADS_ENABLED,
        "conversions_api": settings.META_CONVERSIONS_API_ENABLED,
    }


def meta_configuration_status() -> dict[str, bool]:
    """Return presence/safety signals only; never return a secret or callback URL."""
    redirect = urlparse(settings.META_OAUTH_REDIRECT_BASE_URL)
    return {
        "app_credentials": bool(settings.META_APP_ID and settings.META_APP_SECRET),
        "instagram_app_credentials": bool(
            settings.META_INSTAGRAM_APP_ID and settings.META_INSTAGRAM_APP_SECRET
        ),
        "webhook_verify_token": bool(settings.META_WEBHOOK_VERIFY_TOKEN),
        "oauth_redirect_configured": bool(redirect.scheme and redirect.netloc),
        "oauth_redirect_https": redirect.scheme == "https",
        "embedded_signup_config": bool(settings.META_WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID),
        "credential_encryption_key": bool(settings.META_CREDENTIAL_ENCRYPTION_KEY),
    }


class MetaFeatureFlagService:
    @staticmethod
    async def effective(db: AsyncSession, broker_id: int) -> dict[str, Any]:
        broker = await db.scalar(select(Broker).where(Broker.id == broker_id))
        if not broker:
            raise HTTPException(status_code=404, detail="Broker no encontrado")
        configured = dict(broker.meta_features or {})
        tenant_enabled = bool(
            configured.get("enabled", settings.META_BROKER_DEFAULT_ENABLED)
        )
        globals_ = _global_switches()
        parent_app_configured = bool(settings.META_APP_ID and settings.META_APP_SECRET)
        instagram_app_configured = bool(
            settings.META_INSTAGRAM_APP_ID and settings.META_INSTAGRAM_APP_SECRET
        )
        channels = {
            key: bool(
                settings.META_FEATURE_ENABLED
                and tenant_enabled
                and globals_[key]
                and configured.get(key, True)
                and (instagram_app_configured if key == "instagram" else parent_app_configured)
            )
            for key in FEATURE_KEYS
        }
        return {
            "configured": parent_app_configured,
            "global_enabled": settings.META_FEATURE_ENABLED,
            "broker_enabled": tenant_enabled,
            "channels": channels,
            "overrides": {key: configured[key] for key in configured if key in {"enabled", *FEATURE_KEYS}},
        }

    @staticmethod
    async def require(
        db: AsyncSession,
        *,
        broker_id: int,
        feature: str,
    ) -> None:
        state = await MetaFeatureFlagService.effective(db, broker_id)
        if not state["configured"]:
            raise HTTPException(status_code=503, detail="La aplicación Meta no está configurada")
        if not state["channels"].get(feature, False):
            raise HTTPException(status_code=503, detail="Esta función Meta no está habilitada para el broker")

    @staticmethod
    async def update(
        db: AsyncSession,
        *,
        current_user: dict,
        changes: dict[str, bool],
    ) -> dict[str, Any]:
        if str(current_user.get("role") or "").upper() != UserRole.ADMIN.value:
            raise HTTPException(status_code=403, detail="Jefatura debe administrar estos permisos")
        broker_id = int(current_user["broker_id"])
        broker = await db.scalar(select(Broker).where(Broker.id == broker_id))
        if not broker:
            raise HTTPException(status_code=404, detail="Broker no encontrado")
        before = dict(broker.meta_features or {})
        after = dict(before)
        after.update({key: bool(value) for key, value in changes.items() if key in {"enabled", *FEATURE_KEYS}})
        broker.meta_features = after
        raw_uid = current_user.get("user_id") or current_user.get("id")
        db.add(AuditLog(
            user_id=int(raw_uid) if raw_uid is not None else None,
            broker_id=broker_id,
            action="meta_feature_flags_updated",
            resource_type="broker",
            resource_id=broker_id,
            changes={"before": before, "after": after},
        ))
        await db.commit()
        return await MetaFeatureFlagService.effective(db, broker_id)
