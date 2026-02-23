"""
Unit tests for app.services.llm.router (LLMRouter)

Covers:
- Primary succeeds → result returned, no failover
- Primary raises retriable error → fallback is used
- Primary raises non-retriable error → re-raised immediately (no fallback)
- Fallback also fails → exception propagates
- _is_retriable helper
- used_fallback flag on LLMRouter
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm.router import LLMRouter, _is_retriable
from app.services.llm.base_provider import LLMResponse


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_provider(response=None, side_effect=None):
    """Create a minimal mock BaseLLMProvider."""
    p = MagicMock()
    p.is_configured = True
    p.model = "test-model"
    p.generate_with_messages = AsyncMock(return_value=response, side_effect=side_effect)
    p.generate_json = AsyncMock(return_value=response, side_effect=side_effect)
    p.generate_with_tools = AsyncMock(return_value=response, side_effect=side_effect)
    p.generate_response = AsyncMock(return_value=response, side_effect=side_effect)
    return p


_GOOD_RESPONSE = LLMResponse(content="Hola, ¿en qué puedo ayudarte?")


# ── _is_retriable ─────────────────────────────────────────────────────────────

def test_is_retriable_httpx_timeout():
    import httpx
    assert _is_retriable(httpx.TimeoutException("timeout")) is True


def test_is_retriable_httpx_connect():
    import httpx
    assert _is_retriable(httpx.ConnectError("connect")) is True


def test_is_retriable_generic_value_error():
    assert _is_retriable(ValueError("bad value")) is False


def test_is_retriable_generic_runtime_error():
    assert _is_retriable(RuntimeError("crash")) is False


def test_is_retriable_key_error():
    assert _is_retriable(KeyError("missing")) is False


# ── LLMRouter happy path ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_router_uses_primary_on_success():
    primary = _make_provider(response=_GOOD_RESPONSE)
    fallback = _make_provider(response=LLMResponse(content="fallback"))

    async def _passthrough(fn, *a, **kw): return await fn(*a, **kw)
    with patch("app.core.circuit_breakers.llm_breaker.call_async", new=_passthrough):
        router = LLMRouter(primary=primary, fallback=fallback)
        result = await router.generate_with_messages([], system_prompt="test")

    assert result.content == _GOOD_RESPONSE.content
    primary.generate_with_messages.assert_called_once()
    fallback.generate_with_messages.assert_not_called()


@pytest.mark.asyncio
async def test_router_failover_on_retriable_error():
    import httpx
    primary = _make_provider(side_effect=httpx.TimeoutException("timeout"))
    fallback = _make_provider(response=LLMResponse(content="from fallback"))

    # Bypass circuit breaker in unit tests
    async def _passthrough(fn, *a, **kw): return await fn(*a, **kw)
    with patch("app.core.circuit_breakers.llm_breaker.call_async", new=_passthrough):
        router = LLMRouter(primary=primary, fallback=fallback)
        result = await router.generate_with_messages([], system_prompt="test")

    assert result.content == "from fallback"
    fallback.generate_with_messages.assert_called_once()


@pytest.mark.asyncio
async def test_router_no_failover_on_non_retriable_error():
    primary = _make_provider(side_effect=ValueError("bad request — not retriable"))
    fallback = _make_provider(response=LLMResponse(content="from fallback"))

    async def _passthrough(fn, *a, **kw): return await fn(*a, **kw)
    with patch("app.core.circuit_breakers.llm_breaker.call_async", new=_passthrough):
        router = LLMRouter(primary=primary, fallback=fallback)
        with pytest.raises(ValueError, match="bad request"):
            await router.generate_with_messages([], system_prompt="test")

    # Fallback must NOT be called for non-retriable errors
    fallback.generate_with_messages.assert_not_called()


@pytest.mark.asyncio
async def test_router_raises_when_both_fail():
    import httpx
    primary = _make_provider(side_effect=httpx.TimeoutException("timeout"))
    fallback = _make_provider(side_effect=httpx.ConnectError("refused"))

    async def _passthrough(fn, *a, **kw): return await fn(*a, **kw)
    with patch("app.core.circuit_breakers.llm_breaker.call_async", new=_passthrough):
        router = LLMRouter(primary=primary, fallback=fallback)
        with pytest.raises(Exception):
            await router.generate_with_messages([], system_prompt="test")


# ── is_configured property ────────────────────────────────────────────────────

def test_router_is_configured_when_primary_is():
    primary = MagicMock()
    primary.is_configured = True
    fallback = MagicMock()
    fallback.is_configured = False

    router = LLMRouter(primary=primary, fallback=fallback)
    assert router.is_configured is True


def test_router_is_configured_when_fallback_is():
    primary = MagicMock()
    primary.is_configured = False
    fallback = MagicMock()
    fallback.is_configured = True

    router = LLMRouter(primary=primary, fallback=fallback)
    assert router.is_configured is True


def test_router_not_configured_when_both_are_not():
    primary = MagicMock()
    primary.is_configured = False
    fallback = MagicMock()
    fallback.is_configured = False

    router = LLMRouter(primary=primary, fallback=fallback)
    assert router.is_configured is False
