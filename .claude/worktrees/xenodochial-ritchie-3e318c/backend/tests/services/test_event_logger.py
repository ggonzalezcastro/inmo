"""
Tests for AgentEventLogger — fire-and-forget contract, no-raise on error,
Redis publish side-effect.

Run without DB:
    python -m pytest tests/services/test_event_logger.py -v --noconftest
"""
from __future__ import annotations

import asyncio
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.observability.event_logger import AgentEventLogger


# ── No-raise contract ─────────────────────────────────────────────────────────

class TestEventLoggerNoRaise:
    @pytest.mark.asyncio
    async def test_log_llm_call_never_raises_on_db_error(self):
        logger = AgentEventLogger()
        with patch(
            "app.services.observability.event_logger.AgentEventLogger._write",
            new_callable=AsyncMock,
            side_effect=RuntimeError("DB is down"),
        ):
            # Should not raise — fire-and-forget
            await logger.log_llm_call(
                lead_id=1, broker_id=1,
                provider="gemini", model="gemini-2.5-flash",
                input_tokens=100, output_tokens=50,
                latency_ms=800, cost_usd=0.001,
                agent_type="qualifier",
            )

    @pytest.mark.asyncio
    async def test_log_error_never_raises(self):
        logger = AgentEventLogger()
        with patch(
            "app.services.observability.event_logger.AgentEventLogger._write",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Redis gone"),
        ):
            await logger.log_error(
                lead_id=1, broker_id=1,
                error_type="LLMError",
                error_message="timeout",
                agent_type="qualifier",
            )

    @pytest.mark.asyncio
    async def test_log_handoff_never_raises(self):
        logger = AgentEventLogger()
        with patch(
            "app.services.observability.event_logger.AgentEventLogger._write",
            new_callable=AsyncMock,
            side_effect=Exception("generic"),
        ):
            await logger.log_handoff(
                lead_id=1, broker_id=1,
                from_agent="qualifier", to_agent="scheduler",
                reason="qualified",
            )


# ── Write is called asynchronously ───────────────────────────────────────────

class TestEventLoggerFireAndForget:
    @pytest.mark.asyncio
    async def test_log_schedules_write(self):
        """_log should schedule _write via ensure_future without awaiting it."""
        logger = AgentEventLogger()
        write_calls = []

        async def fake_write(**kwargs):
            write_calls.append(kwargs)

        with patch.object(logger, "_write", side_effect=fake_write):
            await logger.log_agent_selected(
                lead_id=1, broker_id=1,
                agent_type="qualifier",
                reason="stage=entrada",
            )
            # give the event loop a tick to run the future
            await asyncio.sleep(0)

        assert len(write_calls) == 1
        assert write_calls[0]["event_type"] == "agent_selected"

    @pytest.mark.asyncio
    async def test_llm_call_write_receives_correct_fields(self):
        logger = AgentEventLogger()
        captured = {}

        async def fake_write(**kwargs):
            captured.update(kwargs)

        with patch.object(logger, "_write", side_effect=fake_write):
            await logger.log_llm_call(
                lead_id=42, broker_id=7,
                provider="claude", model="claude-3-5-sonnet",
                input_tokens=200, output_tokens=80,
                latency_ms=1200, cost_usd=0.003,
                agent_type="scheduler",
            )
            await asyncio.sleep(0)

        assert captured.get("event_type") == "llm_call"
        assert captured.get("lead_id") == 42
        assert captured.get("broker_id") == 7
        assert captured.get("llm_provider") == "claude"
        assert captured.get("input_tokens") == 200


# ── Redis publish ─────────────────────────────────────────────────────────────

class TestEventLoggerRedisPublish:
    @pytest.mark.asyncio
    async def test_write_publishes_to_redis(self):
        """_write should publish to obs:live:{broker_id} after DB write."""
        logger = AgentEventLogger()
        mock_event = MagicMock()
        mock_event.created_at = None

        mock_redis = AsyncMock()
        mock_db_instance = AsyncMock()
        mock_db_instance.add = MagicMock()
        mock_db_instance.commit = AsyncMock()
        mock_db_instance.refresh = AsyncMock()
        mock_db_instance.__aenter__ = AsyncMock(return_value=mock_db_instance)
        mock_db_instance.__aexit__ = AsyncMock(return_value=False)

        mock_db_module = MagicMock()
        mock_db_module.AsyncSessionLocal = MagicMock(return_value=mock_db_instance)
        mock_agent_event_cls = MagicMock(return_value=mock_event)
        mock_event_module = MagicMock(AgentEvent=mock_agent_event_cls)

        # Patch sys.modules for both lazy imports inside _write()
        with patch.dict("sys.modules", {
                "app.core.database": mock_db_module,
                "app.models.agent_event": mock_event_module,
             }), \
             patch("app.core.redis_client._get_async_redis", return_value=mock_redis):
            await logger._write(event_type="llm_call", lead_id=1, broker_id=5)

        mock_redis.publish.assert_called_once()
        channel_arg = mock_redis.publish.call_args[0][0]
        assert "obs:live:5" in channel_arg

    @pytest.mark.asyncio
    async def test_write_does_not_raise_if_redis_fails(self):
        """Redis publish failure must not propagate."""
        logger = AgentEventLogger()
        mock_event = MagicMock()
        mock_event.created_at = None

        mock_redis = AsyncMock()
        mock_redis.publish = AsyncMock(side_effect=ConnectionError("Redis down"))

        mock_db_instance = AsyncMock()
        mock_db_instance.add = MagicMock()
        mock_db_instance.commit = AsyncMock()
        mock_db_instance.refresh = AsyncMock()
        mock_db_instance.__aenter__ = AsyncMock(return_value=mock_db_instance)
        mock_db_instance.__aexit__ = AsyncMock(return_value=False)

        mock_db_module2 = MagicMock()
        mock_db_module2.AsyncSessionLocal = MagicMock(return_value=mock_db_instance)
        mock_event_module2 = MagicMock(AgentEvent=MagicMock(return_value=mock_event))

        with patch.dict("sys.modules", {
                "app.core.database": mock_db_module2,
                "app.models.agent_event": mock_event_module2,
             }), \
             patch("app.core.redis_client._get_async_redis", return_value=mock_redis):
            # Should not raise
            await logger._write(event_type="error", lead_id=1, broker_id=5)
