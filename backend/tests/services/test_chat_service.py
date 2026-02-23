"""
Tests for ChatService (get_provider_for_broker, log_message, handle_webhook).
Uses mocks for DB and providers where needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat import ChatService
from app.services.chat.base_provider import ChatMessageData


class TestChatService:
    """Tests for ChatService."""

    @pytest.mark.asyncio
    async def test_get_broker_chat_config_none_when_no_config(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=AsyncMock(return_value=None)))
        config = await ChatService.get_broker_chat_config(db, broker_id=1)
        assert config is None

    @pytest.mark.asyncio
    async def test_get_provider_for_broker_none_when_no_config(self):
        db = AsyncMock()
        with patch.object(ChatService, "get_broker_chat_config", AsyncMock(return_value=None)):
            provider = await ChatService.get_provider_for_broker(db, broker_id=1, provider_name="telegram")
        assert provider is None

    @pytest.mark.asyncio
    async def test_get_provider_for_broker_returns_provider_when_configured(self):
        db = AsyncMock()
        mock_config = MagicMock()
        mock_config.enabled_providers = ["telegram"]
        mock_config.provider_configs = {"telegram": {"bot_token": "test"}}
        with patch.object(ChatService, "get_broker_chat_config", AsyncMock(return_value=mock_config)):
            provider = await ChatService.get_provider_for_broker(db, broker_id=1, provider_name="telegram")
        assert provider is not None
        assert provider.get_provider_name() == "telegram"

    @pytest.mark.asyncio
    async def test_get_provider_for_broker_none_when_provider_not_enabled(self):
        db = AsyncMock()
        mock_config = MagicMock()
        mock_config.enabled_providers = ["whatsapp"]
        mock_config.provider_configs = {"whatsapp": {}}
        with patch.object(ChatService, "get_broker_chat_config", AsyncMock(return_value=mock_config)):
            provider = await ChatService.get_provider_for_broker(db, broker_id=1, provider_name="telegram")
        assert provider is None

    @pytest.mark.asyncio
    async def test_send_message_returns_error_when_provider_unavailable(self):
        db = AsyncMock()
        with patch.object(ChatService, "get_provider_for_broker", AsyncMock(return_value=None)):
            result = await ChatService.send_message(
                db, broker_id=1, provider_name="telegram", channel_user_id="123", message_text="Hi"
            )
        assert result.success is False
        assert "not available" in (result.error or "")
