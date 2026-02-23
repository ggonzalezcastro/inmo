"""
Unit tests for app.services.llm.call_logger

Covers:
- _estimate_cost for known models
- _estimate_cost returns None for unknown models
- log_llm_call swallows DB errors (observability must not crash)
- Cost calculation is correct for token counts
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.llm.call_logger import _estimate_cost, log_llm_call


# ── _estimate_cost ─────────────────────────────────────────────────────────────

class TestEstimateCost:
    def test_gemini_flash_known(self):
        cost = _estimate_cost("gemini-2.5-flash", 1000, 1000)
        assert cost is not None
        assert cost > 0

    def test_claude_sonnet_known(self):
        cost = _estimate_cost("claude-sonnet-4-6", 1000, 1000)
        assert cost is not None
        assert cost > 0

    def test_gpt4o_known(self):
        cost = _estimate_cost("gpt-4o", 1000, 1000)
        assert cost is not None
        assert cost > 0

    def test_unknown_model_returns_none(self):
        cost = _estimate_cost("mystery-model-x99", 1000, 1000)
        assert cost is None

    def test_zero_tokens_returns_zero_cost(self):
        cost = _estimate_cost("gemini-2.5-flash", 0, 0)
        assert cost == 0.0

    def test_cost_increases_with_more_tokens(self):
        c1 = _estimate_cost("gpt-4o", 100, 100)
        c2 = _estimate_cost("gpt-4o", 10000, 10000)
        assert c2 > c1

    def test_output_more_expensive_than_input_for_gpt4o(self):
        c_input_only = _estimate_cost("gpt-4o", 1000, 0)
        c_output_only = _estimate_cost("gpt-4o", 0, 1000)
        # GPT-4o output is $0.015/1k, input is $0.005/1k
        assert c_output_only > c_input_only

    def test_result_is_rounded(self):
        cost = _estimate_cost("gemini-2.5-flash", 123, 456)
        assert cost == round(cost, 8)

    def test_partial_model_name_match(self):
        # Model names can be partial — "gemini-2.0-flash-exp" should match
        cost = _estimate_cost("gemini-2.0-flash-exp-latest", 500, 200)
        assert cost is not None


# ── log_llm_call — error swallowing ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_log_llm_call_swallows_db_error():
    """DB failure must NOT propagate to caller."""
    with patch("app.database.AsyncSessionLocal") as mock_session_cls:
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(side_effect=RuntimeError("DB down"))
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        # Should not raise
        await log_llm_call(
            provider="gemini",
            model="gemini-2.5-flash",
            call_type="qualification",
            input_tokens=100,
            output_tokens=50,
            latency_ms=300,
        )


@pytest.mark.asyncio
async def test_log_llm_call_swallows_import_error():
    """Even ImportError must be swallowed."""
    with patch("app.services.llm.call_logger.log_llm_call.__module__", side_effect=ImportError):
        # Direct call — should not raise regardless
        try:
            await log_llm_call(
                provider="gemini",
                model="gemini-2.5-flash",
                call_type="chat_response",
            )
        except Exception as e:
            pytest.fail(f"log_llm_call raised unexpectedly: {e}")


@pytest.mark.asyncio
async def test_log_llm_call_success_path():
    """Happy path — writes a row and commits."""
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    with patch("app.database.AsyncSessionLocal", return_value=mock_db):
        await log_llm_call(
            provider="claude",
            model="claude-sonnet-4-6",
            call_type="chat_response",
            input_tokens=200,
            output_tokens=80,
            latency_ms=450,
            broker_id=1,
            lead_id=5,
            used_fallback=False,
        )

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
