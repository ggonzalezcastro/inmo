"""
Tests for AgentModelConfig — per-broker, per-agent LLM configuration.

Run without DB:
    python -m pytest tests/services/test_agent_model_config.py -v --noconftest
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_row(
    agent_type: str = "qualifier",
    llm_provider: str = "gemini",
    llm_model: str = "gemini-2.5-flash",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    is_active: bool = True,
    broker_id: int = 1,
    row_id: int = 1,
):
    """Build a mock AgentModelConfig ORM row."""
    row = MagicMock()
    row.id = row_id
    row.broker_id = broker_id
    row.agent_type = agent_type
    row.llm_provider = llm_provider
    row.llm_model = llm_model
    row.temperature = temperature
    row.max_tokens = max_tokens
    row.is_active = is_active
    row.created_at = None
    row.updated_at = None
    return row


# ── model_config service ──────────────────────────────────────────────────────

class TestAgentModelConfigService:

    @pytest.mark.asyncio
    async def test_cache_miss_queries_db(self):
        """On cache miss, the service fetches from DB and populates cache."""
        from app.services.agents.model_config import load_all_agent_configs

        fake_row = _make_row(agent_type="qualifier")
        fake_db = AsyncMock()
        fake_result = MagicMock()
        fake_result.scalars.return_value.all.return_value = [fake_row]
        fake_db.execute = AsyncMock(return_value=fake_result)

        with patch("app.services.agents.model_config.cache_get_json", AsyncMock(return_value=None)), \
             patch("app.services.agents.model_config.cache_set_json", AsyncMock(return_value=True)):
            configs = await load_all_agent_configs(broker_id=1, db=fake_db)

        assert "qualifier" in configs
        assert configs["qualifier"]["llm_provider"] == "gemini"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db(self):
        """On cache hit, the service never touches the DB."""
        from app.services.agents.model_config import load_all_agent_configs

        cached = {"qualifier": {"id": 1, "broker_id": 1, "agent_type": "qualifier",
                                 "llm_provider": "claude", "llm_model": "claude-3",
                                 "temperature": None, "max_tokens": None, "is_active": True}}
        fake_db = AsyncMock()

        with patch("app.services.agents.model_config.cache_get_json", AsyncMock(return_value=cached)):
            configs = await load_all_agent_configs(broker_id=1, db=fake_db)

        fake_db.execute.assert_not_called()
        assert configs["qualifier"]["llm_provider"] == "claude"

    @pytest.mark.asyncio
    async def test_get_agent_model_config_returns_none_if_missing(self):
        """Returns None when no config is set for the agent."""
        from app.services.agents.model_config import get_agent_model_config

        fake_db = AsyncMock()
        with patch("app.services.agents.model_config.load_all_agent_configs", AsyncMock(return_value={})):
            result = await get_agent_model_config(broker_id=1, agent_type="scheduler", db=fake_db)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_deletes_cache_key(self):
        """Invalidation calls cache_delete with the correct key."""
        from app.services.agents.model_config import invalidate_agent_configs

        mock_delete = AsyncMock(return_value=True)
        with patch("app.services.agents.model_config.cache_delete", mock_delete):
            await invalidate_agent_configs(broker_id=42)

        mock_delete.assert_called_once_with("agent_model_config:42")

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self):
        """delete_agent_model_config returns False when row doesn't exist."""
        from app.services.agents.model_config import delete_agent_model_config

        fake_db = AsyncMock()
        fake_result = MagicMock()
        fake_result.scalars.return_value.first.return_value = None
        fake_db.execute = AsyncMock(return_value=fake_result)

        result = await delete_agent_model_config(broker_id=1, agent_type="qualifier", db=fake_db)
        assert result is False


# ── factory: build_provider_from_config ──────────────────────────────────────

class TestBuildProviderFromConfig:

    def test_cache_same_config_returns_same_instance(self):
        """Two calls with identical config return the same provider instance."""
        from app.services.llm.factory import build_provider_from_config, reset_provider

        reset_provider()
        with patch("app.services.llm.factory._build_provider", MagicMock(side_effect=lambda n: MagicMock(is_configured=True))), \
             patch("app.services.llm.factory.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "key"
            mock_settings.GEMINI_TEMPERATURE = 0.7
            mock_settings.GEMINI_MAX_TOKENS = 1500
            mock_settings.LLM_FALLBACK_PROVIDER = ""

            # Import GeminiProvider mock
            with patch("app.services.llm.gemini_provider.GeminiProvider") as mock_gemini:
                instance_a = MagicMock(is_configured=True)
                mock_gemini.return_value = instance_a

                p1 = build_provider_from_config("gemini", "gemini-2.5-flash", 0.7, 1500)
                p2 = build_provider_from_config("gemini", "gemini-2.5-flash", 0.7, 1500)
                assert p1 is p2, "Expected same cached instance for identical config"

        reset_provider()

    def test_different_model_returns_different_instance(self):
        """Different models produce distinct provider instances."""
        from app.services.llm.factory import build_provider_from_config, reset_provider

        reset_provider()
        with patch("app.services.llm.factory.settings") as mock_settings, \
             patch("app.services.llm.gemini_provider.GeminiProvider") as mock_gemini:
            mock_settings.GEMINI_API_KEY = "key"
            mock_settings.GEMINI_TEMPERATURE = 0.7
            mock_settings.GEMINI_MAX_TOKENS = 1500
            mock_settings.LLM_FALLBACK_PROVIDER = ""

            mock_gemini.side_effect = lambda **kw: MagicMock(is_configured=True, model=kw.get("model"))

            p1 = build_provider_from_config("gemini", "gemini-2.0-flash", 0.7, 1500)
            p2 = build_provider_from_config("gemini", "gemini-2.5-pro", 0.7, 1500)
            assert p1 is not p2, "Expected different instances for different models"

        reset_provider()

    def test_resolves_none_temperature_to_default(self):
        """When temperature=None, uses the provider env default (not 0.0)."""
        from app.services.llm.factory import _get_provider_defaults

        temp, tokens = _get_provider_defaults("gemini")
        assert isinstance(temp, float)
        assert isinstance(tokens, int)
        assert temp > 0.0


# ── factory: resolve_provider_for_agent ──────────────────────────────────────

class TestResolveProviderForAgent:

    @pytest.mark.asyncio
    async def test_returns_global_when_no_config(self):
        """Falls back to global provider when no per-agent config exists."""
        from app.services.llm.factory import resolve_provider_for_agent

        global_provider = MagicMock()
        fake_db = AsyncMock()

        with patch("app.services.agents.model_config.get_agent_model_config", AsyncMock(return_value=None)), \
             patch("app.services.llm.factory.get_llm_provider", return_value=global_provider):
            result = await resolve_provider_for_agent("qualifier", 1, fake_db)

        assert result is global_provider

    @pytest.mark.asyncio
    async def test_returns_custom_provider_when_config_exists(self):
        """Returns a custom provider when broker has a config for the agent."""
        from app.services.llm.factory import resolve_provider_for_agent

        config = {
            "llm_provider": "claude",
            "llm_model": "claude-3-haiku",
            "temperature": 0.5,
            "max_tokens": 1024,
            "is_active": True,
        }
        custom_provider = MagicMock(is_configured=True)
        fake_db = AsyncMock()

        with patch("app.services.agents.model_config.get_agent_model_config", AsyncMock(return_value=config)), \
             patch("app.services.llm.factory.build_provider_from_config", return_value=custom_provider):
            result = await resolve_provider_for_agent("scheduler", 1, fake_db)

        assert result is custom_provider

    @pytest.mark.asyncio
    async def test_falls_back_to_global_when_provider_not_configured(self):
        """Falls back to global when custom provider lacks an API key."""
        from app.services.llm.factory import resolve_provider_for_agent

        config = {
            "llm_provider": "openai",
            "llm_model": "gpt-4o",
            "temperature": None,
            "max_tokens": None,
            "is_active": True,
        }
        # Custom provider is NOT configured (no API key)
        unconfigured = MagicMock(is_configured=False)
        global_provider = MagicMock()
        fake_db = AsyncMock()

        with patch("app.services.agents.model_config.get_agent_model_config", AsyncMock(return_value=config)), \
             patch("app.services.llm.factory.build_provider_from_config", return_value=unconfigured), \
             patch("app.services.llm.factory.get_llm_provider", return_value=global_provider):
            result = await resolve_provider_for_agent("property", 1, fake_db)

        assert result is global_provider

    @pytest.mark.asyncio
    async def test_falls_back_to_global_when_config_inactive(self):
        """Inactive config is treated as if no config exists."""
        from app.services.llm.factory import resolve_provider_for_agent

        config = {
            "llm_provider": "claude",
            "llm_model": "claude-3",
            "temperature": None,
            "max_tokens": None,
            "is_active": False,  # <-- inactive
        }
        global_provider = MagicMock()
        fake_db = AsyncMock()

        with patch("app.services.agents.model_config.get_agent_model_config", AsyncMock(return_value=config)), \
             patch("app.services.llm.factory.get_llm_provider", return_value=global_provider):
            result = await resolve_provider_for_agent("follow_up", 1, fake_db)

        assert result is global_provider


# ── Schema validation ─────────────────────────────────────────────────────────

class TestAgentModelConfigSchemas:

    def test_valid_create(self):
        from app.schemas.agent_model_config import AgentModelConfigCreate
        cfg = AgentModelConfigCreate(
            agent_type="qualifier",
            llm_provider="gemini",
            llm_model="gemini-2.5-flash",
        )
        assert cfg.agent_type == "qualifier"
        assert cfg.is_active is True

    def test_invalid_agent_type(self):
        from app.schemas.agent_model_config import AgentModelConfigCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="agent_type"):
            AgentModelConfigCreate(
                agent_type="invalid_agent",
                llm_provider="gemini",
                llm_model="gemini-2.5-flash",
            )

    def test_invalid_provider(self):
        from app.schemas.agent_model_config import AgentModelConfigCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="llm_provider"):
            AgentModelConfigCreate(
                agent_type="qualifier",
                llm_provider="unknown_provider",
                llm_model="some-model",
            )

    def test_temperature_zero_is_valid(self):
        """temperature=0.0 should be allowed (tests the 'if v is not None' fix)."""
        from app.schemas.agent_model_config import AgentModelConfigCreate
        cfg = AgentModelConfigCreate(
            agent_type="qualifier",
            llm_provider="claude",
            llm_model="claude-3-haiku",
            temperature=0.0,
        )
        assert cfg.temperature == 0.0

    def test_temperature_out_of_range(self):
        from app.schemas.agent_model_config import AgentModelConfigCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="temperature"):
            AgentModelConfigCreate(
                agent_type="qualifier",
                llm_provider="claude",
                llm_model="claude-3",
                temperature=3.0,
            )

    def test_max_tokens_boundary(self):
        from app.schemas.agent_model_config import AgentModelConfigCreate
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="max_tokens"):
            AgentModelConfigCreate(
                agent_type="scheduler",
                llm_provider="openai",
                llm_model="gpt-4o",
                max_tokens=99,  # below minimum of 100
            )
