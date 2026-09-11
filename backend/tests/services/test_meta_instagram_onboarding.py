"""Instagram Login asset synchronization across corporate and personal owners."""

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.broker import Broker
from app.models.meta import MetaAsset, MetaConnection, MetaCredential
from app.models.user import User, UserRole
from app.services.meta.onboarding import complete_connection


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("owner_type", "role", "expected_owner_user", "expected_status"),
    [
        ("broker", UserRole.ADMIN, False, "active"),
        ("user", UserRole.AGENT, True, "paused"),
    ],
)
async def test_instagram_asset_sync_copies_connection_owner_and_is_idempotent(
    db_session,
    monkeypatch,
    owner_type,
    role,
    expected_owner_user,
    expected_status,
):
    monkeypatch.setattr(settings, "META_INSTAGRAM_APP_ID", "sandbox-instagram-app")
    monkeypatch.setattr(
        settings,
        "META_INSTAGRAM_APP_SECRET",
        "sandbox-instagram-app-secret",
    )
    monkeypatch.setattr(settings, "META_CREDENTIAL_ENCRYPTION_KEY", "k" * 48)

    broker = Broker(name=f"Instagram {owner_type}")
    db_session.add(broker)
    await db_session.flush()
    user = User(
        email=f"{owner_type}@example.test",
        hashed_password="not-a-real-password-hash",
        name=f"Instagram {owner_type}",
        role=role,
        broker_id=broker.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    principal_id = f"ig-{owner_type}-123"
    username = f"captame_{owner_type}"

    async def meta_handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.instagram.com":
            return httpx.Response(
                200,
                json={"access_token": "sandbox-access", "user_id": principal_id},
            )
        if request.url.host == "graph.instagram.com" and request.url.path.endswith(
            "/access_token"
        ):
            return httpx.Response(
                200,
                json={"access_token": "sandbox-long-access", "expires_in": 5_184_000},
            )
        if request.url.host == "graph.instagram.com":
            return httpx.Response(
                200,
                json={
                    "user_id": principal_id,
                    "username": username,
                    "account_type": "BUSINESS",
                },
            )
        if request.url.host == "graph.facebook.com" and request.method == "POST":
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404, json={"error": {"message": "unexpected test request"}})

    claims = {
        "broker_id": broker.id,
        "user_id": user.id,
        "channel": "instagram",
        "owner_type": owner_type,
    }
    transport = httpx.MockTransport(meta_handler)

    first_connection = await complete_connection(
        db_session,
        channel="instagram",
        code="first-code",
        claims=claims,
        transport=transport,
    )
    first_asset = await db_session.scalar(select(MetaAsset))

    assert first_connection.owner_type == owner_type
    assert first_asset is not None
    assert first_asset.asset_type == "instagram_account"
    assert first_asset.channel == "instagram"
    assert first_asset.external_id == principal_id
    assert first_asset.display_name == username
    assert first_asset.owner_type == owner_type
    assert first_asset.owner_user_id == (user.id if expected_owner_user else None)
    assert first_asset.status == expected_status
    first_asset_id = first_asset.id

    await complete_connection(
        db_session,
        channel="instagram",
        code="second-code",
        claims=claims,
        transport=transport,
    )

    assert await db_session.scalar(select(func.count(MetaConnection.id))) == 1
    assert await db_session.scalar(select(func.count(MetaAsset.id))) == 1
    repeated_asset = await db_session.scalar(select(MetaAsset))
    assert repeated_asset is not None
    assert repeated_asset.id == first_asset_id
    assert repeated_asset.channel == "instagram"
    assert repeated_asset.external_id == principal_id
    assert repeated_asset.display_name == username
    assert repeated_asset.owner_type == owner_type
    assert repeated_asset.owner_user_id == (user.id if expected_owner_user else None)

    credential = await db_session.scalar(select(MetaCredential))
    assert credential is not None
    assert credential.encrypted_token not in {"sandbox-access", "sandbox-long-access"}
    assert credential.encrypted_token.startswith("meta:v1:")
