"""OAuth, connection, and asset APIs for the multi-tenant Meta integration."""

from __future__ import annotations

from typing import List, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.schemas.meta import (
    MetaAssetResponse,
    MetaAssetUpdate,
    MetaAuthorizeResponse,
    MetaConnectionComplete,
    MetaConnectionResponse,
    MetaFeatureUpdate,
    MetaMessageTemplateResponse,
)
from app.services.meta.connections import MetaAssetService, MetaConnectionService
from app.services.meta.oauth import MetaOAuthStateError, MetaOAuthStateService
from app.services.meta.onboarding import (
    CHANNEL_CONFIG,
    authorization_url,
    complete_connection,
)
from app.services.meta.feature_flags import MetaFeatureFlagService, meta_configuration_status
from app.services.meta.health import MetaConnectionHealthService, MetaMessageTemplateService

router = APIRouter()


def _feature_for_channel(channel: str) -> str:
    return {
        "whatsapp": "whatsapp",
        "instagram": "instagram",
        "messenger": "messenger",
        "business": "ads",
    }[channel]


def _identity(user: dict) -> tuple[int, int, str]:
    if user.get("broker_id") is None:
        raise HTTPException(status_code=400, detail="Usuario sin broker asignado")
    raw_uid = user.get("user_id") or user.get("id")
    try:
        uid = int(raw_uid)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Identidad de usuario inválida") from exc
    return int(user["broker_id"]), uid, str(user.get("role") or "").upper()


def _owner_for_channel(channel: str, role: str) -> str:
    if channel in {"whatsapp", "business"}:
        if role != "ADMIN":
            raise HTTPException(status_code=403, detail="Jefatura debe conectar este canal")
        return "broker"
    if role == "ADMIN":
        return "broker"
    if role == "AGENT":
        return "executive"
    raise HTTPException(status_code=403, detail="Permiso insuficiente")


@router.get("/health")
async def meta_health(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    broker_id, _, _ = _identity(current_user)
    state = await MetaFeatureFlagService.effective(db, broker_id)
    state["graph_api_version"] = settings.META_GRAPH_API_VERSION
    state["configuration"] = meta_configuration_status()
    state["legacy_whatsapp_fallback_enabled"] = (
        settings.META_WHATSAPP_LEGACY_FALLBACK_ENABLED
    )
    return state


@router.patch("/features")
async def update_meta_features(
    body: MetaFeatureUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    state = await MetaFeatureFlagService.update(
        db,
        current_user=current_user,
        changes=body.model_dump(exclude_unset=True),
    )
    state["graph_api_version"] = settings.META_GRAPH_API_VERSION
    state["configuration"] = meta_configuration_status()
    state["legacy_whatsapp_fallback_enabled"] = (
        settings.META_WHATSAPP_LEGACY_FALLBACK_ENABLED
    )
    return state


@router.post(
    "/connections/{channel}/authorize",
    response_model=MetaAuthorizeResponse,
)
async def start_authorization(
    channel: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if channel not in CHANNEL_CONFIG:
        raise HTTPException(status_code=404, detail="Canal Meta no soportado")
    broker_id, user_id, role = _identity(current_user)
    await MetaFeatureFlagService.require(
        db,
        broker_id=broker_id,
        feature=_feature_for_channel(channel),
    )
    owner_type = _owner_for_channel(channel, role)
    state = await MetaOAuthStateService.issue(
        broker_id=broker_id,
        user_id=user_id,
        channel=channel,
        owner_type=owner_type,
    )
    return MetaAuthorizeResponse(
        authorization_url=authorization_url(channel, state),
        state=state,
        channel=channel,
    )


@router.post(
    "/connections/{channel}/complete",
    response_model=MetaConnectionResponse,
)
async def complete_authorization(
    channel: str,
    body: MetaConnectionComplete,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    broker_id, user_id, _ = _identity(current_user)
    if channel not in CHANNEL_CONFIG:
        raise HTTPException(status_code=404, detail="Canal Meta no soportado")
    await MetaFeatureFlagService.require(
        db,
        broker_id=broker_id,
        feature=_feature_for_channel(channel),
    )
    try:
        claims = await MetaOAuthStateService.consume(body.state)
        if int(claims["broker_id"]) != broker_id or int(claims["user_id"]) != user_id:
            raise MetaOAuthStateError("OAuth state pertenece a otra sesión")
        connection = await complete_connection(
            db,
            channel=channel,
            code=body.code,
            claims=claims,
            waba_id=body.waba_id,
            phone_number_id=body.phone_number_id,
            display_name=body.display_name,
            metadata=body.metadata,
        )
        return MetaConnectionResponse.model_validate(connection)
    except (MetaOAuthStateError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/connections/{channel}/callback", include_in_schema=False)
async def oauth_callback(
    channel: str,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    _error_description: Optional[str] = Query(None, alias="error_description"),
    waba_id: Optional[str] = Query(None),
    phone_number_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    frontend = f"{settings.FRONTEND_URL.rstrip('/')}/my-channels"
    if error or not code or not state:
        return RedirectResponse(
            f"{frontend}?{urlencode({'meta': 'error', 'code': error or 'oauth_cancelled'})}"
        )
    try:
        claims = await MetaOAuthStateService.consume(state)
        await MetaFeatureFlagService.require(
            db,
            broker_id=int(claims["broker_id"]),
            feature=_feature_for_channel(channel),
        )
        connection = await complete_connection(
            db,
            channel=channel,
            code=code,
            claims=claims,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
        )
        return RedirectResponse(
            f"{frontend}?{urlencode({'meta': 'connected', 'connection_id': connection.id})}"
        )
    except Exception:
        return RedirectResponse(
            f"{frontend}?{urlencode({'meta': 'error', 'code': 'connection_failed'})}"
        )


@router.get("/connections", response_model=List[MetaConnectionResponse])
async def list_connections(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await MetaConnectionService.list_for_user(db, current_user)


@router.delete("/connections/{connection_id}", response_model=MetaConnectionResponse)
async def disconnect_connection(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await MetaConnectionService.disconnect(
        db,
        connection_id=connection_id,
        current_user=current_user,
    )


@router.post(
    "/connections/{connection_id}/revalidate",
    response_model=MetaConnectionResponse,
)
async def revalidate_connection(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    broker_id, _, _ = _identity(current_user)
    return await MetaConnectionHealthService.revalidate(
        db,
        connection_id=connection_id,
        broker_id=broker_id,
        current_user=current_user,
    )


@router.post("/connections/{connection_id}/sync")
async def synchronize_connection_assets(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    broker_id, _, role = _identity(current_user)
    if role != "ADMIN":
        raise HTTPException(status_code=403, detail="Jefatura debe sincronizar los activos")
    count = await MetaConnectionHealthService.sync_assets(
        db,
        connection_id=connection_id,
        broker_id=broker_id,
        current_user=current_user,
    )
    return {"ok": True, "asset_count": count}


@router.get("/assets", response_model=List[MetaAssetResponse])
async def list_assets(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await MetaAssetService.list_for_user(db, current_user)


@router.patch("/assets/{asset_id}", response_model=MetaAssetResponse)
async def update_asset(
    asset_id: int,
    body: MetaAssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    return await MetaAssetService.update(
        db,
        asset_id=asset_id,
        current_user=current_user,
        changes=body.model_dump(exclude_unset=True),
    )


@router.get(
    "/assets/{asset_id}/message-templates",
    response_model=List[MetaMessageTemplateResponse],
)
async def list_whatsapp_message_templates(
    asset_id: int,
    approved_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    broker_id, _, _ = _identity(current_user)
    return await MetaMessageTemplateService.list_for_phone(
        db,
        broker_id=broker_id,
        phone_asset_id=asset_id,
        approved_only=approved_only,
    )
