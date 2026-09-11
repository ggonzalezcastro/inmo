"""Meta OAuth completion and capability-safe asset discovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.meta_encryption import encrypt_meta_secret
from app.models.meta import MetaAsset, MetaCredential
from app.services.meta.client import MetaGraphClient, MetaGraphError
from app.services.meta.connections import MetaConnectionService


CHANNEL_CONFIG = {
    "whatsapp": {
        "auth_mode": "whatsapp_embedded_signup",
        "scopes": [
            "business_management",
            "whatsapp_business_management",
            "whatsapp_business_messaging",
        ],
    },
    "instagram": {
        "auth_mode": "instagram_login",
        "scopes": [
            "instagram_business_basic",
            "instagram_business_manage_messages",
        ],
    },
    "messenger": {
        "auth_mode": "business_login",
        "scopes": [
            "pages_show_list",
            "pages_read_engagement",
            "pages_manage_metadata",
            "pages_messaging",
        ],
    },
    "business": {
        "auth_mode": "business_login",
        "scopes": [
            "business_management",
            "pages_show_list",
            "pages_read_engagement",
            "pages_manage_metadata",
            "pages_messaging",
            "instagram_basic",
            "instagram_manage_messages",
            "ads_read",
            "ads_management",
            "leads_retrieval",
        ],
    },
}


def redirect_uri(channel: str) -> str:
    return f"{settings.META_OAUTH_REDIRECT_BASE_URL.rstrip('/')}/connections/{channel}/callback"


def authorization_url(channel: str, state: str) -> str:
    config = CHANNEL_CONFIG[channel]
    params: Dict[str, Any] = {
        "client_id": (
            settings.META_INSTAGRAM_APP_ID
            if channel == "instagram"
            else settings.META_APP_ID
        ),
        "redirect_uri": redirect_uri(channel),
        "response_type": "code",
        "state": state,
        "scope": ",".join(config["scopes"]),
    }
    if channel == "instagram":
        params.update({"enable_fb_login": "0", "force_authentication": "1"})
        return f"https://www.instagram.com/oauth/authorize?{urlencode(params)}"
    if channel == "whatsapp" and settings.META_WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID:
        params["config_id"] = settings.META_WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID
    return (
        f"https://www.facebook.com/{settings.META_GRAPH_API_VERSION}/dialog/oauth?"
        f"{urlencode(params)}"
    )


async def exchange_code(
    channel: str,
    code: str,
    *,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> Dict[str, Any]:
    if channel == "instagram":
        url = "https://api.instagram.com/oauth/access_token"
        data = {
            "client_id": settings.META_INSTAGRAM_APP_ID,
            "client_secret": settings.META_INSTAGRAM_APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri(channel),
            "code": code,
        }
        async with httpx.AsyncClient(transport=transport, timeout=20.0) as client:
            response = await client.post(url, data=data)
    else:
        url = f"https://graph.facebook.com/{settings.META_GRAPH_API_VERSION}/oauth/access_token"
        params = {
            "client_id": settings.META_APP_ID,
            "client_secret": settings.META_APP_SECRET,
            "redirect_uri": redirect_uri(channel),
            "code": code,
        }
        async with httpx.AsyncClient(transport=transport, timeout=20.0) as client:
            response = await client.get(url, params=params)
    if response.is_error:
        raise ValueError("Meta rechazó la autorización; vuelve a intentarlo")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("Meta devolvió una respuesta de autorización inválida") from exc
    if not payload.get("access_token"):
        raise ValueError("Meta no devolvió un access token")
    if channel == "instagram":
        short_lived_token = str(payload["access_token"])
        params = {
            "grant_type": "ig_exchange_token",
            "client_secret": settings.META_INSTAGRAM_APP_SECRET,
            "access_token": short_lived_token,
        }
        async with httpx.AsyncClient(transport=transport, timeout=20.0) as client:
            long_lived_response = await client.get(
                "https://graph.instagram.com/access_token",
                params=params,
            )
        if long_lived_response.is_error:
            raise ValueError("Instagram rechazó la conversión a token de larga duración")
        try:
            long_lived_payload = long_lived_response.json()
        except ValueError as exc:
            raise ValueError("Instagram devolvió una respuesta de token inválida") from exc
        if not long_lived_payload.get("access_token"):
            raise ValueError("Instagram no devolvió un token de larga duración")
        payload = {**payload, **long_lived_payload}
    return payload


async def _upsert_asset(
    db: AsyncSession,
    *,
    broker_id: int,
    connection_id: int,
    asset_type: str,
    channel: Optional[str],
    external_id: str,
    display_name: Optional[str],
    owner_type: str,
    owner_user_id: Optional[int],
    capabilities: Iterable[str],
    parent_external_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    access_token: Optional[str] = None,
) -> MetaAsset:
    asset = await db.scalar(
        select(MetaAsset).where(
            MetaAsset.asset_type == asset_type,
            MetaAsset.external_id == str(external_id),
        )
    )
    if asset and asset.broker_id != broker_id:
        raise ValueError("El activo Meta ya está asociado a otro broker")
    if not asset:
        asset = MetaAsset(
            broker_id=broker_id,
            connection_id=connection_id,
            asset_type=asset_type,
            external_id=str(external_id),
        )
        db.add(asset)
        await db.flush()
    asset.connection_id = connection_id
    asset.channel = channel
    asset.parent_external_id = parent_external_id
    asset.display_name = display_name
    asset.owner_type = owner_type
    asset.owner_user_id = owner_user_id if owner_type == "executive" else None
    asset.capabilities = sorted(set(capabilities))
    asset.approval_status = "approved" if owner_type == "broker" else "pending_approval"
    asset.status = "active" if owner_type == "broker" else "paused"
    asset.asset_metadata = metadata or {}
    asset.last_synced_at = datetime.now(timezone.utc)

    if access_token:
        credential = await db.scalar(
            select(MetaCredential).where(
                MetaCredential.connection_id == connection_id,
                MetaCredential.subject_type == "asset",
                MetaCredential.subject_external_id == str(external_id),
            )
        )
        if not credential:
            credential = MetaCredential(
                broker_id=broker_id,
                connection_id=connection_id,
                asset_id=asset.id,
                subject_type="asset",
                subject_external_id=str(external_id),
            )
            db.add(credential)
        credential.asset_id = asset.id
        credential.encrypted_token = encrypt_meta_secret(access_token)
        credential.status = "active"
    return asset


async def discover_conversion_datasets(
    graph: MetaGraphClient,
    ad_accounts: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Discover normalized conversion datasets without failing OAuth on missing access."""
    datasets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for account in ad_accounts:
        account_id = str(account.get("id") or "")
        if not account_id:
            continue
        try:
            async for remote in graph.iterate(
                f"{account_id}/adspixels",
                params={"fields": "id,name", "limit": 100},
            ):
                external_id = str(remote.get("id") or "")
                if not external_id or external_id in seen:
                    continue
                seen.add(external_id)
                datasets.append({
                    "id": external_id,
                    "name": remote.get("name") or f"Dataset {external_id}",
                    "ad_account_id": account_id,
                })
        except MetaGraphError:
            # Some valid business connections cannot enumerate pixels until Meta
            # grants the corresponding asset permission. Other assets stay usable.
            continue
    return datasets


async def complete_connection(
    db: AsyncSession,
    *,
    channel: str,
    code: str,
    claims: Dict[str, Any],
    waba_id: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    display_name: Optional[str] = None,
    metadata: Optional[dict] = None,
    transport: Optional[httpx.AsyncBaseTransport] = None,
):
    if channel not in CHANNEL_CONFIG or claims.get("channel") != channel:
        raise ValueError("El canal OAuth no coincide con el estado")
    token_payload = await exchange_code(channel, code, transport=transport)
    access_token = token_payload["access_token"]
    expires_at = None
    if token_payload.get("expires_in"):
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=int(token_payload["expires_in"])
        )
    graph = MetaGraphClient(
        access_token=access_token,
        app_secret=(
            settings.META_INSTAGRAM_APP_SECRET
            if channel == "instagram"
            else settings.META_APP_SECRET
        ),
        base_url=(
            "https://graph.instagram.com"
            if channel == "instagram"
            else "https://graph.facebook.com"
        ),
        transport=transport,
    )

    if channel == "instagram":
        profile = await graph.get(
            "me",
            params={"fields": "user_id,username,account_type"},
        )
        account_type = str(profile.get("account_type") or "").upper()
        if account_type and account_type not in {"BUSINESS", "MEDIA_CREATOR", "CREATOR"}:
            raise ValueError("Instagram debe ser una cuenta profesional Business o Creator")
        principal_id = str(profile.get("user_id") or profile.get("id"))
        principal_name = profile.get("username") or display_name
    else:
        profile = await graph.get("me", params={"fields": "id,name"})
        principal_id = str(waba_id or profile.get("id"))
        principal_name = display_name or profile.get("name")

    broker_id = int(claims["broker_id"])
    user_id = int(claims["user_id"])
    owner_type = str(claims["owner_type"])
    connection = await MetaConnectionService.create_or_update(
        db,
        broker_id=broker_id,
        owner_type=owner_type,
        owner_user_id=user_id if owner_type == "executive" else None,
        connected_by_user_id=user_id,
        auth_mode=CHANNEL_CONFIG[channel]["auth_mode"],
        external_principal_id=principal_id,
        access_token=access_token,
        display_name=principal_name,
        scopes=CHANNEL_CONFIG[channel]["scopes"],
        expires_at=expires_at,
        connection_metadata=metadata or {},
    )

    if channel == "instagram":
        instagram_asset = await _upsert_asset(
            db,
            broker_id=broker_id,
            connection_id=connection.id,
            asset_type="instagram_account",
            channel="instagram",
            external_id=principal_id,
            display_name=principal_name,
            owner_type=owner_type,
            owner_user_id=user_id if owner_type == "executive" else None,
            capabilities=["messaging"],
            metadata={"account_type": profile.get("account_type")},
        )
        try:
            await graph.post(
                f"{principal_id}/subscribed_aps",
                data={"subscribed_fields": "messages,messaging_postbacks"},
            )
            instagram_asset.asset_metadata = {
                **(instagram_asset.asset_metadata or {}),
                "webhook_subscription": "active",
            }
        except MetaGraphError as exc:
            instagram_asset.status = "error"
            instagram_asset.last_error_code = exc.category
            instagram_asset.last_error_detail = "No fue posible suscribir los webhooks de Instagram"
    elif channel == "whatsapp":
        if not waba_id:
            raise ValueError("WhatsApp Embedded Signup debe devolver waba_id")
        await _upsert_asset(
            db,
            broker_id=broker_id,
            connection_id=connection.id,
            asset_type="waba",
            channel="whatsapp",
            external_id=waba_id,
            display_name=principal_name,
            owner_type="broker",
            owner_user_id=None,
            capabilities=["messaging", "templates"],
        )
        phones = []
        if phone_number_id:
            phones = [{"id": phone_number_id, "display_phone_number": display_name}]
        else:
            phone_response = await graph.get(
                f"{waba_id}/phone_numbers",
                params={"fields": "id,display_phone_number,verified_name,quality_rating"},
            )
            phones = phone_response.get("data", [])
        for phone in phones:
            await _upsert_asset(
                db,
                broker_id=broker_id,
                connection_id=connection.id,
                asset_type="whatsapp_phone",
                channel="whatsapp",
                external_id=str(phone["id"]),
                parent_external_id=str(waba_id),
                display_name=phone.get("verified_name") or phone.get("display_phone_number"),
                owner_type="broker",
                owner_user_id=None,
                capabilities=["messaging", "templates"],
                metadata=phone,
            )
    else:
        pages_response = await graph.get(
            "me/accounts",
            params={"fields": "id,name,access_token,instagram_business_account{id,username}"},
        )
        for page in pages_response.get("data", []):
            page_capabilities = ["messaging"]
            if owner_type == "broker":
                page_capabilities.extend(["ads", "leadgen"])
            page_asset = await _upsert_asset(
                db,
                broker_id=broker_id,
                connection_id=connection.id,
                asset_type="facebook_page",
                channel="facebook",
                external_id=str(page["id"]),
                display_name=page.get"name"),
                owner_type=owner_type,
                owner_user_id=user_id if owner_type == "executive" else None,
                capabilities=page_capabilities,
                access_token=page.get("access_token"),
            )
            page_token = page.get("access_token") or access_token
            page_graph = MetaGraphClient(access_token=page_token, transport=transport)
            subscribed_fields = [
                "messages",
                "messaging_postbacks",
                "message_deliveries",
                "message_reads",
            ]
            if owner_type == "broker":
                subscribed_fields.append("leadgen")
            try:
                await page_graph.post(
                    f"{page['id']}/subscribed_aps",
                    data={"subscribed_fields": ",".join(subscribed_fields)},
                )
                page_asset.asset_metadata = {
                    **(page_asset.asset_metadata or {}),
                    "webhook_subscription": "active",
                    "subscribed_fields": subscribed_fields,
                }
            except MetaGraphError as exc:
                page_asset.status = "error"
                page_asset.last_error_code = exc.category
                page_asset.last_error_detail = "No fue posible suscribir los webhooks de la página"
            ig = page.get("instagram_business_account") or {}
            if ig.get("id") and owner_type == "broker":
                await _upsert_asset(
                    db,
                    broker_id=broker_id,
                    connection_id=connection.id,
                    asset_type="instagram_account",
                    channel="instagram",
                    external_id=str(ig["id"]),
                    parent_external_id=str(page["id"]),
                    display_name=ig.get("username") or f"Instagram de {page.get('name') or page['id']}",
                    owner_type="broker",
                    owner_user_id=None,
                    capabilities=["messaging", "ads"],
                )
        if channel == "business":
            accounts = await graph.get(
                "me/adaccounts",
                params={"fields": "id,name,account_status,currency,timezone_name"},
            )
            ad_accounts = accounts.get("data", [])
            for account in ad_accounts:
                account_asset = await _upsert_asset(
                    db,
                    broker_id=broker_id,
                    connection_id=connection.id,
                    asset_type="ad_account",
                    channel=None,
                    external_id=str(account["id"]),
                    display_name=account.get("name"),
                    owner_type="broker",
                    owner_user_id=None,
                    capabilities=["ads", "insights", "leadgen"],
                    metadata=account,
                )
                if int(account.get("account_status") or 0) != 1:
                    account_asset.status = "disabled"
                    account_asset.capabilities = ["insights"]
                    account_asset.last_error_code = "AD_ACCOUNT_RESTRICTED"
                    account_asset.last_error_detail = "La cuenta publicitaria está restringida o inactiva en Meta"

            for dataset in await discover_conversion_datasets(graph, ad_accounts):
                await _upsert_asset(
                    db,
                    broker_id=broker_id,
                    connection_id=connection.id,
                    asset_type="pixel",
                    channel=None,
                    external_id=dataset["id"],
                    parent_external_id=dataset["ad_account_id"],
                    display_name=dataset["name"],
                    owner_type="broker",
                    owner_user_id=None,
                    capabilities=["conversions"],
                    metadata={
                        "ad_account_id": dataset["ad_account_id"],
                        "source": "adspixels",
                    },
                )

    await db.commit()
    return connection
