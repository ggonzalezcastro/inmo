"""Self-contained tests for Meta foundation services (no database required)."""

from urllib.parse import parse_qs, urlparse
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.meta_encryption import (
    MetaEncryptionError,
    decrypt_meta_json,
    decrypt_meta_secret,
    encrypt_meta_json,
    encrypt_meta_secret,
)
from app.services.meta.client import MetaGraphClient, MetaGraphError
from app.services.meta.connections import MetaAssetService
from app.services.meta.oauth import MetaOAuthStateError, MetaOAuthStateService
from app.services.meta.onboarding import authorization_url, discover_conversion_datasets
from app.services.meta.inbox import MetaInboxService
from app.services.meta.feature_flags import meta_configuration_status
from app.services.meta.legacy_audit import (
    migration_readiness_errors,
    retirement_errors,
    summarize_legacy_secret_state,
)
from app.services.meta.metrics import record_legacy_fallback
from app.services.chat.base_provider import SendMessageResult
from app.services.chat.service import ChatService
from app.services.chat.whatsapp_service import WhatsAppService
from app.schemas.meta import MetaAssetResponse, MetaConnectionResponse


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def setex(self, key, ttl, value):
        self.values[key] = value

    async def getdel(self, key):
        return self.values.pop(key, None)


class LegacyRedisWithAtomicEval:
    """Redis-compatible test double for clients without the GETDEL helper."""

    def __init__(self):
        self.values = {}

    async def setex(self, key, ttl, value):
        self.values[key] = value

    async def eval(self, script, key_count, key):
        assert key_count == 1
        assert "GET" in script and "DEL" in script
        return self.values.pop(key, None)


def test_meta_secret_encryption_round_trip(monkeypatch):
    monkeypatch.setattr(settings, "META_CREDENTIAL_ENCRYPTION_KEY", "m" * 48)
    ciphertext = encrypt_meta_secret("EA-test-token")
    assert ciphertext.startswith("meta:v1:")
    assert "EA-test-token" not in ciphertext
    assert decrypt_meta_secret(ciphertext) == "EA-test-token"


def test_meta_json_encryption_round_trip(monkeypatch):
    monkeypatch.setattr(settings, "META_CREDENTIAL_ENCRYPTION_KEY", "j" * 48)
    ciphertext = encrypt_meta_json({"entry": [{"id": "123"}]})
    assert decrypt_meta_json(ciphertext) == {"entry": [{"id": "123"}]}


def test_meta_decryption_rejects_plaintext(monkeypatch):
    monkeypatch.setattr(settings, "META_CREDENTIAL_ENCRYPTION_KEY", "k" * 48)
    with pytest.raises(MetaEncryptionError):
        decrypt_meta_secret("plaintext-token")


def test_public_meta_schemas_never_expose_credentials():
    forbidden = {
        "access_token",
        "app_secret",
        "client_secret",
        "encrypted_token",
        "payload_ciphertext",
    }
    assert forbidden.isdisjoint(MetaConnectionResponse.model_fields)
    assert forbidden.isdisjoint(MetaAssetResponse.model_fields)


def test_meta_configuration_status_exposes_presence_without_values(monkeypatch):
    monkeypatch.setattr(settings, "META_APP_ID", "app-id-secret")
    monkeypatch.setattr(settings, "META_APP_SECRET", "app-secret-value")
    monkeypatch.setattr(settings, "META_WEBHOOK_VERIFY_TOKEN", "verify-secret")
    monkeypatch.setattr(settings, "META_OAUTH_REDIRECT_BASE_URL", "https://staging.example/api/v1/meta")
    monkeypatch.setattr(settings, "META_WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID", "config-secret")
    monkeypatch.setattr(settings, "META_CREDENTIAL_ENCRYPTION_KEY", "encryption-secret")

    status = meta_configuration_status()

    assert status == {
        "app_credentials": True,
        "webhook_verify_token": True,
        "oauth_redirect_configured": True,
        "oauth_redirect_https": True,
        "embedded_signup_config": True,
        "credential_encryption_key": True,
    }
    serialized = repr(status)
    assert "app-secret-value" not in serialized
    assert "verify-secret" not in serialized
    assert "encryption-secret" not in serialized


@pytest.mark.asyncio
async def test_whatsapp_legacy_fallback_is_measured_when_asset_conversation_is_missing(
    monkeypatch,
):
    monkeypatch.setattr(settings, "META_WHATSAPP_ASSET_ROUTING_ENABLED", True)
    monkeypatch.setattr(settings, "META_WHATSAPP_LEGACY_FALLBACK_ENABLED", True)
    provider = SimpleNamespace(
        send_message=AsyncMock(return_value=SendMessageResult(True, "wamid-1"))
    )
    db = SimpleNamespace(add=Mock(), commit=AsyncMock(), refresh=AsyncMock())

    with (
        patch(
            "app.services.meta.outbound.MetaOutboundService.send_for_lead",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            ChatService,
            "get_provider_for_broker",
            new=AsyncMock(return_value=provider),
        ),
        patch("app.services.meta.metrics.record_legacy_fallback") as record_fallback,
    ):
        result = await ChatService.send_message(
            db,
            broker_id=7,
            provider_name="whatsapp",
            channel_user_id="56900000000",
            message_text="test",
            lead_id=9,
        )

    assert result.success is True
    record_fallback.assert_called_once_with(
        "outbound", "missing_asset_conversation", "used"
    )


@pytest.mark.asyncio
async def test_whatsapp_legacy_fallback_can_be_retired_without_silent_send(
    monkeypatch,
):
    monkeypatch.setattr(settings, "META_WHATSAPP_ASSET_ROUTING_ENABLED", True)
    monkeypatch.setattr(settings, "META_WHATSAPP_LEGACY_FALLBACK_ENABLED", False)

    with (
        patch(
            "app.services.meta.outbound.MetaOutboundService.send_for_lead",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            ChatService,
            "get_provider_for_broker",
            new=AsyncMock(),
        ) as get_provider,
        patch("app.services.meta.metrics.record_legacy_fallback") as record_fallback,
    ):
        result = await ChatService.send_message(
            AsyncMock(),
            broker_id=7,
            provider_name="whatsapp",
            channel_user_id="56900000000",
            message_text="test",
            lead_id=9,
        )

    assert result.success is False
    assert result.error and result.error.startswith("LEGACY_WHATSAPP_FALLBACK_DISABLED")
    get_provider.assert_not_awaited()
    record_fallback.assert_called_once_with(
        "outbound", "missing_asset_conversation", "blocked"
    )


def test_legacy_secret_audit_confirms_encrypted_asset_mapping_without_values():
    config = SimpleNamespace(
        broker_id=7,
        provider_configs={
            "whatsapp": {
                "phone_number_id": "asset-1",
                "access_token": "legacy-token",
                "verify_token": "legacy-verify",
            }
        },
    )
    asset = SimpleNamespace(
        id=11,
        broker_id=7,
        connection_id=5,
        asset_type="whatsapp_phone",
        external_id="asset-1",
    )
    credential = SimpleNamespace(
        broker_id=7,
        connection_id=5,
        asset_id=None,
        status="active",
        encrypted_token="meta:v1:ciphertext",
    )

    report = summarize_legacy_secret_state(
        configs=[config],
        assets=[asset],
        credentials=[credential],
        legacy_environment={"WHATSAPP_ACCESS_TOKEN": False},
        fallback_enabled=True,
    )

    assert report.legacy_plaintext_secret_fields == 2
    assert report.migrated_access_token_configs == 1
    assert report.migration_gaps == 0
    assert migration_readiness_errors(report) == []
    assert "legacy-token" not in repr(report)
    assert "legacy-verify" not in repr(report)


def test_legacy_secret_audit_requires_clean_storage_and_disabled_fallback():
    report = summarize_legacy_secret_state(
        configs=[
            SimpleNamespace(
                broker_id=7,
                provider_configs={"whatsapp": {"phone_number_id": "asset-1"}},
            )
        ],
        assets=[],
        credentials=[
            SimpleNamespace(
                broker_id=7,
                connection_id=5,
                asset_id=None,
                status="active",
                encrypted_token="meta:v1:ciphertext",
            )
        ],
        legacy_environment={},
        fallback_enabled=False,
    )

    assert report.legacy_plaintext_secret_fields == 0
    assert report.legacy_environment_variables_present == 0
    assert retirement_errors(report) == []


def test_legacy_fallback_log_uses_only_low_cardinality_labels(caplog):
    caplog.set_level("INFO", logger="app.services.meta.metrics")

    record_legacy_fallback("outbound", "missing_lead_id", "blocked")

    assert (
        "direction=outbound reason=missing_lead_id result=blocked" in caplog.text
    )


@pytest.mark.asyncio
async def test_inbox_access_query_scopes_conversation_and_lead_to_broker():
    result = Mock()
    result.first.return_value = None
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    with pytest.raises(HTTPException) as captured:
        await MetaInboxService.assert_access(
            db,
            conversation_id=99,
            current_user={"id": 12, "broker_id": 7, "role": "ADMIN"},
        )

    assert captured.value.status_code == 404
    statement = str(db.execute.await_args.args[0])
    assert "conversations.broker_id" in statement
    assert "leads.broker_id" in statement


@pytest.mark.asyncio
async def test_oauth_state_is_single_use(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "s" * 48)
    redis = FakeRedis()
    state = await MetaOAuthStateService.issue(
        broker_id=7,
        user_id=12,
        channel="instagram",
        owner_type="executive",
        redis_client=redis,
    )
    claims = await MetaOAuthStateService.consume(state, redis_client=redis)
    assert claims["broker_id"] == 7
    assert claims["user_id"] == 12
    with pytest.raises(MetaOAuthStateError):
        await MetaOAuthStateService.consume(state, redis_client=redis)


@pytest.mark.asyncio
async def test_oauth_state_fallback_is_atomic_and_single_use(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "s" * 48)
    redis = LegacyRedisWithAtomicEval()
    state = await MetaOAuthStateService.issue(
        broker_id=7,
        user_id=12,
        channel="messenger",
        owner_type="broker",
        redis_client=redis,
    )

    assert (await MetaOAuthStateService.consume(state, redis_client=redis))["broker_id"] == 7
    with pytest.raises(MetaOAuthStateError):
        await MetaOAuthStateService.consume(state, redis_client=redis)


@pytest.mark.asyncio
async def test_oauth_state_fails_closed_without_atomic_redis_command(monkeypatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "s" * 48)
    redis = SimpleNamespace(setex=AsyncMock())
    state = await MetaOAuthStateService.issue(
        broker_id=7,
        user_id=12,
        channel="instagram",
        owner_type="executive",
        redis_client=redis,
    )

    with pytest.raises(MetaOAuthStateError, match="forma segura"):
        await MetaOAuthStateService.consume(state, redis_client=redis)


@pytest.mark.asyncio
async def test_graph_client_adds_appsecret_proof_and_parses_success():
    captured = {}

    async def handler(request: httpx.Request):
        captured["query"] = dict(request.url.params)
        return httpx.Response(200, json={"data": [{"id": "1"}]})

    client = MetaGraphClient(
        "token-123",
        app_secret="secret-456",
        transport=httpx.MockTransport(handler),
    )
    payload = await client.get("me/accounts")
    assert payload["data"][0]["id"] == "1"
    assert captured["query"]["access_token"] == "token-123"
    assert len(captured["query"]["appsecret_proof"]) == 64


@pytest.mark.asyncio
async def test_graph_client_maps_rate_limit_without_leaking_token():
    async def handler(request: httpx.Request):
        return httpx.Response(
            429,
            json={
                "error": {
                    "message": "Limit reached for very-secret",
                    "code": 4,
                    "fbtrace_id": "trace",
                }
            },
        )

    client = MetaGraphClient("very-secret", transport=httpx.MockTransport(handler))
    with pytest.raises(MetaGraphError) as captured:
        await client.get("me")
    assert captured.value.category == "RATE_LIMITED"
    assert "very-secret" not in str(captured.value)


@pytest.mark.asyncio
async def test_graph_pagination_cannot_forward_token_to_another_host():
    requested_hosts = []

    async def handler(request: httpx.Request):
        requested_hosts.append(request.url.host)
        return httpx.Response(
            200,
            json={
                "data": [{"id": "1"}],
                "paging": {"next": "https://attacker.example/collect"},
            },
        )

    client = MetaGraphClient(
        "very-secret",
        app_secret="app-secret",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ValueError, match="graph.facebook.com"):
        _ = [item async for item in client.iterate("me/accounts")]

    assert requested_hosts == ["graph.facebook.com"]


@pytest.mark.asyncio
async def test_legacy_whatsapp_logs_exclude_phone_message_and_provider_body(
    monkeypatch,
    caplog,
):
    phone = "56911112222"
    message = "Mensaje privado del cliente"
    provider_body = f"error for {phone}: {message}"

    class FakeResponse:
        status_code = 400
        text = provider_body

        @staticmethod
        def json():
            return {"error": "rejected"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient())
    caplog.set_level("INFO")
    service = WhatsAppService(phone_number_id="asset-1", access_token="secret-token")

    await service.send_text_message(phone, message)

    assert phone not in caplog.text
    assert message not in caplog.text
    assert provider_body not in caplog.text
    assert "secret-token" not in caplog.text


def test_instagram_authorization_url_requests_messaging_only(monkeypatch):
    monkeypatch.setattr(settings, "META_APP_ID", "123")
    url = authorization_url("instagram", "signed-state")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "www.instagram.com"
    assert query["state"] == ["signed-state"]
    scopes = set(query["scope"][0].split(","))
    assert scopes == {
        "instagram_business_basic",
        "instagram_business_manage_messages",
    }
    assert "ads_management" not in scopes


@pytest.mark.asyncio
async def test_conversion_datasets_are_discovered_from_broker_ad_accounts():
    class FakeGraph:
        async def iterate(self, path, *, params):
            assert params["fields"] == "id,name"
            account_id = path.split("/", 1)[0]
            yield {"id": f"pixel-{account_id}", "name": f"Dataset {account_id}"}

    datasets = await discover_conversion_datasets(
        FakeGraph(),
        [{"id": "act_10"}, {"id": "act_20"}],
    )

    assert datasets == [
        {"id": "pixel-act_10", "name": "Dataset act_10", "ad_account_id": "act_10"},
        {"id": "pixel-act_20", "name": "Dataset act_20", "ad_account_id": "act_20"},
    ]


@pytest.mark.asyncio
async def test_admin_can_select_only_a_corporate_conversion_dataset():
    dataset = SimpleNamespace(
        id=17,
        broker_id=7,
        asset_type="pixel",
        channel=None,
        owner_type="broker",
        approval_status="approved",
        status="active",
        capabilities=["conversions"],
        is_default=False,
    )
    db = SimpleNamespace(
        scalar=AsyncMock(return_value=dataset),
        execute=AsyncMock(),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    updated = await MetaAssetService.update(
        db,
        asset_id=17,
        current_user={"id": 3, "broker_id": 7, "role": "ADMIN"},
        changes={"is_default": True},
    )

    assert updated.is_default is True
    db.execute.assert_awaited_once()

    dataset.owner_type = "executive"
    dataset.is_default = False
    with pytest.raises(HTTPException) as captured:
        await MetaAssetService.update(
            db,
            asset_id=17,
            current_user={"id": 3, "broker_id": 7, "role": "ADMIN"},
            changes={"is_default": True},
        )
    assert captured.value.status_code == 422

    dataset.owner_type = "broker"
    dataset.is_default = True
    dataset.status = "active"
    await MetaAssetService.update(
        db,
        asset_id=17,
        current_user={"id": 3, "broker_id": 7, "role": "ADMIN"},
        changes={"status": "paused"},
    )
    assert dataset.status == "paused"
    assert dataset.is_default is False
