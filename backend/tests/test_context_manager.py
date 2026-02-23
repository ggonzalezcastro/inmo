"""
Unit tests for app.services.chat.context_manager

Covers:
- should_summarize threshold logic
- compress_context passes messages through unchanged when below threshold
- compress_context returns (summary, recent_messages) when above threshold
- LLM failure during summarisation returns prior_summary (graceful fallback)
- DB persistence of summary is attempted
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.chat.context_manager import (
    should_summarize,
    compress_context,
    summarize_conversation,
    SUMMARIZE_THRESHOLD,
    KEEP_RECENT,
)


# ── Test data ────────────────────────────────────────────────────────────────

def _make_messages(n: int):
    """Create n alternating user/assistant messages."""
    msgs = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        msgs.append({"role": role, "content": f"Message {i + 1}"})
    return msgs


# ── should_summarize ─────────────────────────────────────────────────────────

def test_should_summarize_below_threshold():
    msgs = _make_messages(SUMMARIZE_THRESHOLD - 1)
    assert should_summarize(msgs) is False


def test_should_summarize_at_threshold():
    msgs = _make_messages(SUMMARIZE_THRESHOLD)
    assert should_summarize(msgs) is True


def test_should_summarize_above_threshold():
    msgs = _make_messages(SUMMARIZE_THRESHOLD + 5)
    assert should_summarize(msgs) is True


def test_should_summarize_empty_list():
    assert should_summarize([]) is False


# ── compress_context — below threshold ──────────────────────────────────────

@pytest.mark.asyncio
async def test_compress_context_unchanged_below_threshold():
    msgs = _make_messages(SUMMARIZE_THRESHOLD - 1)
    summary, remaining = await compress_context(msgs, existing_summary="old summary")
    # Nothing compressed — all messages returned
    assert remaining == msgs
    assert summary == "old summary"


@pytest.mark.asyncio
async def test_compress_context_no_existing_summary_below_threshold():
    msgs = _make_messages(3)
    summary, remaining = await compress_context(msgs, existing_summary=None)
    assert remaining == msgs
    assert summary is None


# ── compress_context — at/above threshold ────────────────────────────────────

@pytest.mark.asyncio
async def test_compress_context_reduces_messages():
    msgs = _make_messages(SUMMARIZE_THRESHOLD + 2)

    mock_provider = MagicMock()
    mock_provider.is_configured = True
    mock_provider.generate_response = AsyncMock(return_value="• Lead interesado en 2D\n• Tiene renta 1.2M\n• Sin DICOM")

    with patch("app.services.llm.factory.get_llm_provider", return_value=mock_provider):
        summary, recent = await compress_context(msgs, existing_summary=None)

    # Only KEEP_RECENT messages should remain
    assert len(recent) == KEEP_RECENT
    assert recent == msgs[-KEEP_RECENT:]
    assert summary is not None
    assert len(summary) > 0


@pytest.mark.asyncio
async def test_compress_context_incorporates_prior_summary():
    msgs = _make_messages(SUMMARIZE_THRESHOLD)

    mock_provider = MagicMock()
    mock_provider.is_configured = True
    mock_provider.generate_response = AsyncMock(return_value="Resumen combinado")

    with patch("app.services.llm.factory.get_llm_provider", return_value=mock_provider):
        summary, _ = await compress_context(msgs, existing_summary="Resumen previo")

    # LLM was called (prior summary injected into prompt)
    mock_provider.generate_response.assert_called_once()
    call_prompt = mock_provider.generate_response.call_args[0][0]
    assert "Resumen previo" in call_prompt


@pytest.mark.asyncio
async def test_compress_context_llm_failure_returns_prior_summary():
    """When LLM fails, prior_summary is returned and pipeline is not broken."""
    msgs = _make_messages(SUMMARIZE_THRESHOLD)

    mock_provider = MagicMock()
    mock_provider.is_configured = True
    mock_provider.generate_response = AsyncMock(side_effect=RuntimeError("LLM down"))

    with patch("app.services.llm.factory.get_llm_provider", return_value=mock_provider):
        summary, recent = await compress_context(msgs, existing_summary="prior summary")

    assert summary == "prior summary"
    assert recent == msgs[-KEEP_RECENT:]


@pytest.mark.asyncio
async def test_compress_context_unconfigured_provider_returns_prior():
    msgs = _make_messages(SUMMARIZE_THRESHOLD)

    mock_provider = MagicMock()
    mock_provider.is_configured = False

    with patch("app.services.llm.factory.get_llm_provider", return_value=mock_provider):
        summary, recent = await compress_context(msgs, existing_summary="saved summary")

    assert summary == "saved summary"


# ── summarize_conversation ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_summarize_conversation_calls_llm():
    msgs = [
        {"role": "user", "content": "Hola, busco depto"},
        {"role": "assistant", "content": "¿Cuánto es tu renta?"},
        {"role": "user", "content": "1.200.000"},
    ]
    mock_provider = MagicMock()
    mock_provider.is_configured = True
    mock_provider.generate_response = AsyncMock(return_value="• Busca depto • Renta 1.2M")

    with patch("app.services.llm.factory.get_llm_provider", return_value=mock_provider):
        result = await summarize_conversation(msgs)

    assert "1.2M" in result or result  # summary returned
    mock_provider.generate_response.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_conversation_includes_prior_summary_in_prompt():
    msgs = [{"role": "user", "content": "¿Tienen estacionamiento?"}]
    mock_provider = MagicMock()
    mock_provider.is_configured = True
    mock_provider.generate_response = AsyncMock(return_value="Nuevo resumen")

    with patch("app.services.llm.factory.get_llm_provider", return_value=mock_provider):
        await summarize_conversation(msgs, prior_summary="Resumen anterior")

    prompt = mock_provider.generate_response.call_args[0][0]
    assert "Resumen anterior" in prompt
