"""
Unit tests for chat providers (Telegram, WhatsApp).
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.chat.base_provider import ChatMessageData, SendMessageResult
from app.services.chat.telegram_provider import TelegramProvider
from app.services.chat.whatsapp_provider import WhatsAppProvider
from app.services.chat.factory import ChatProviderFactory


class TestTelegramProvider:
    """Tests for TelegramProvider."""

    @pytest.fixture
    def provider(self):
        return TelegramProvider(config={"bot_token": "test_token", "webhook_secret": "secret"})

    @pytest.mark.asyncio
    async def test_parse_webhook_message_text(self, provider):
        payload = {
            "update_id": 123,
            "message": {
                "message_id": 456,
                "from": {"id": 789, "username": "testuser"},
                "chat": {"id": 789},
                "text": "Hello",
                "date": 1234567890,
            },
        }
        result = await provider.parse_webhook_message(payload)
        assert result is not None
        assert isinstance(result, ChatMessageData)
        assert result.channel_user_id == "789"
        assert result.channel_username == "testuser"
        assert result.message_text == "Hello"
        assert result.direction == "in"
        assert result.channel_message_id == "456"

    @pytest.mark.asyncio
    async def test_parse_webhook_message_empty_returns_none(self, provider):
        assert await provider.parse_webhook_message({}) is None
        assert await provider.parse_webhook_message({"update_id": 1}) is None

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_with_secret(self, provider):
        assert await provider.verify_webhook_signature({}, "secret") is True
        assert await provider.verify_webhook_signature({}, "wrong") is False

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_no_secret_returns_true(self):
        p = TelegramProvider(config={"bot_token": "t"})
        assert await p.verify_webhook_signature({}, "") is True

    def test_get_provider_name(self, provider):
        assert provider.get_provider_name() == "telegram"

    @pytest.mark.asyncio
    async def test_send_message_success(self, provider):
        with patch("app.services.chat.telegram_provider.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True, "result": {"message_id": 999}}
            mock_response.text = "{}"
            mock_post = AsyncMock(return_value=mock_response)
            inst = AsyncMock()
            inst.post = mock_post
            mock_client.return_value.__aenter__.return_value = inst
            mock_client.return_value.__aexit__.return_value = None

            result = await provider.send_message("123", "Hello")
            assert result.success is True
            assert result.message_id == "999"


class TestWhatsAppProvider:
    """Tests for WhatsAppProvider."""

    @pytest.fixture
    def provider(self):
        return WhatsAppProvider(
            config={
                "phone_number_id": "123",
                "access_token": "token",
                "verify_token": "verify",
                "app_secret": "secret",
            }
        )

    @pytest.mark.asyncio
    async def test_parse_webhook_message_text(self, provider):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "bid",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "123"},
                                "messages": [
                                    {
                                        "from": "5491112345678",
                                        "id": "wamid.xxx",
                                        "timestamp": "1234567890",
                                        "type": "text",
                                        "text": {"body": "Hello"},
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        result = await provider.parse_webhook_message(payload)
        assert result is not None
        assert result.channel_user_id == "5491112345678"
        assert result.message_text == "Hello"
        assert result.direction == "in"
        assert result.channel_message_id == "wamid.xxx"

    @pytest.mark.asyncio
    async def test_parse_webhook_message_empty_returns_none(self, provider):
        assert await provider.parse_webhook_message({}) is None
        assert await provider.parse_webhook_message({"entry": []}) is None

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_no_app_secret_returns_true(self):
        p = WhatsAppProvider(config={"phone_number_id": "1", "access_token": "t"})
        assert await p.verify_webhook_signature({}, "any") is True

    def test_get_provider_name(self, provider):
        assert provider.get_provider_name() == "whatsapp"


class TestChatProviderFactory:
    """Tests for ChatProviderFactory."""

    def test_create_telegram(self):
        provider = ChatProviderFactory.create("telegram", {"bot_token": "t"})
        assert provider is not None
        assert provider.get_provider_name() == "telegram"

    def test_create_whatsapp(self):
        provider = ChatProviderFactory.create(
            "whatsapp",
            {"phone_number_id": "1", "access_token": "t"},
        )
        assert provider is not None
        assert provider.get_provider_name() == "whatsapp"

    def test_create_unsupported_raises(self):
        with pytest.raises(ValueError, match="Unsupported chat provider"):
            ChatProviderFactory.create("unknown", {})

    def test_get_supported_providers(self):
        supported = ChatProviderFactory.get_supported_providers()
        assert "telegram" in supported
        assert "whatsapp" in supported
