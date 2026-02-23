"""
LLM Router — automatic failover between providers.

The router wraps a primary and a fallback LLM provider.
When the primary raises a retriable error (rate limit, connection error, timeout)
the router transparently retries once and, if it still fails, delegates the call
to the fallback provider.

Usage (via factory.py — transparent to the rest of the codebase):
    provider = get_llm_provider()   # Returns LLMRouter when fallback is configured
    response = await provider.generate_with_messages(messages, system_prompt)

Error hierarchy handled:
    - httpx.TimeoutException / httpx.ConnectError
    - google.api_core.exceptions.ServiceUnavailable / ResourceExhausted
    - anthropic.APIConnectionError / RateLimitError / APIStatusError (5xx)
    - openai.APIConnectionError / RateLimitError / APIError (5xx)
    - Any other exception treated as non-retriable → re-raised immediately
"""
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services.llm.base_provider import (
    BaseLLMProvider,
    LLMMessage,
    LLMResponse,
    LLMToolDefinition,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retriable exception types (imported lazily to avoid hard dependencies)
# ---------------------------------------------------------------------------

def _is_retriable(exc: Exception) -> bool:
    """
    Return True if the exception represents a transient error worth retrying.
    Checks known exception types from all supported providers.
    """
    exc_type = type(exc)
    exc_module = exc_type.__module__ or ""

    # httpx network errors (shared by all providers)
    try:
        import httpx
        if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
            return True
    except ImportError:
        pass

    # Google Gemini errors
    if "google" in exc_module:
        try:
            from google.api_core.exceptions import (
                ServiceUnavailable,
                ResourceExhausted,
                DeadlineExceeded,
            )
            if isinstance(exc, (ServiceUnavailable, ResourceExhausted, DeadlineExceeded)):
                return True
        except ImportError:
            pass

    # Anthropic Claude errors
    if "anthropic" in exc_module:
        try:
            import anthropic
            if isinstance(exc, (anthropic.APIConnectionError, anthropic.RateLimitError)):
                return True
            # 5xx server errors
            if isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500:
                return True
        except ImportError:
            pass

    # OpenAI errors
    if "openai" in exc_module:
        try:
            import openai
            if isinstance(exc, (openai.APIConnectionError, openai.RateLimitError)):
                return True
            if isinstance(exc, openai.APIError) and hasattr(exc, "status_code") and exc.status_code >= 500:
                return True
        except ImportError:
            pass

    return False


# ---------------------------------------------------------------------------
# LLMRouter
# ---------------------------------------------------------------------------

class LLMRouter(BaseLLMProvider):
    """
    Wraps a primary and fallback provider.
    On retriable errors from primary, delegates to fallback.
    Non-retriable errors (bad API key, invalid request) are re-raised immediately.
    """

    def __init__(self, primary: BaseLLMProvider, fallback: BaseLLMProvider):
        # Do NOT call super().__init__ — router has no own API key / model
        self.primary = primary
        self.fallback = fallback
        self._failover_active = False  # Tracks if we're in fallback mode

    # ── BaseLLMProvider required properties ──────────────────────────────────

    @property
    def is_configured(self) -> bool:
        return self.primary.is_configured or self.fallback.is_configured

    # ── Internal helper ──────────────────────────────────────────────────────

    async def _call_with_failover(self, method_name: str, *args, **kwargs) -> Any:
        """
        Try the primary provider with retries (tenacity), then fall back.

        Flow:
          1. Call primary with up to _MAX_RETRIES retries + exponential backoff.
          2. If all retries exhausted → log WARNING, switch to fallback.
          3. If fallback also fails → propagate exception.
          4. Non-retriable errors (auth, bad request) → raise immediately, no retry/failover.
          5. Each individual API call is wrapped by `llm_breaker` so that a
             consistently unavailable provider is short-circuited quickly.
        """
        from tenacity import (
            AsyncRetrying,
            stop_after_attempt,
            wait_exponential,
            retry_if_exception,
            RetryError,
        )
        from app.core.circuit_breakers import llm_breaker
        import pybreaker

        _MAX_RETRIES = 2  # 2 attempts after the initial call = 3 total
        _WAIT_MIN = 0.5   # seconds
        _WAIT_MAX = 4.0   # seconds

        primary_provider = self.primary
        fallback_provider = self.fallback

        # ── Step 1: try primary with backoff ─────────────────────────────────
        last_primary_exc: Optional[Exception] = None
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(_MAX_RETRIES + 1),
                wait=wait_exponential(multiplier=1, min=_WAIT_MIN, max=_WAIT_MAX),
                retry=retry_if_exception(_is_retriable),
                reraise=False,
            ):
                with attempt:
                    method = getattr(primary_provider, method_name)
                    result = await llm_breaker.call_async(method, *args, **kwargs)

            # Success on primary
            if self._failover_active:
                logger.info(
                    "[LLMRouter] Primary provider recovered",
                    extra={"provider": type(primary_provider).__name__},
                )
                self._failover_active = False
            return result

        except RetryError as retry_err:
            last_primary_exc = retry_err.last_attempt.exception()
            if not _is_retriable(last_primary_exc):
                # Surface non-retriable errors immediately
                raise last_primary_exc from retry_err
            # Retriable — fall through to fallback
            self._failover_active = True
            logger.warning(
                "[LLMRouter] Primary exhausted retries — activating fallback",
                extra={
                    "primary": type(primary_provider).__name__,
                    "fallback": type(fallback_provider).__name__,
                    "error": str(last_primary_exc),
                    "attempts": _MAX_RETRIES + 1,
                },
            )

        except Exception as exc:
            if _is_retriable(exc):
                # Unexpected retriable — go straight to fallback (no retry loop ran)
                self._failover_active = True
                last_primary_exc = exc
                logger.warning(
                    "[LLMRouter] Primary LLM retriable error — activating fallback",
                    extra={
                        "primary": type(primary_provider).__name__,
                        "fallback": type(fallback_provider).__name__,
                        "error": str(exc),
                    },
                )
            else:
                logger.error(
                    "[LLMRouter] Non-retriable error from primary — not using fallback",
                    extra={
                        "provider": type(primary_provider).__name__,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                )
                raise

        # ── Step 2: try fallback ──────────────────────────────────────────────
        try:
            fallback_method = getattr(fallback_provider, method_name)
            return await llm_breaker.call_async(fallback_method, *args, **kwargs)
        except pybreaker.CircuitBreakerError as cb_exc:
            logger.error(
                "[LLMRouter] Circuit breaker OPEN — both providers unavailable",
                extra={"error": str(cb_exc)},
            )
            raise
        except Exception as fallback_exc:
            logger.error(
                "[LLMRouter] Fallback provider also failed",
                extra={
                    "fallback": type(fallback_provider).__name__,
                    "error": str(fallback_exc),
                },
            )
            raise fallback_exc

    # ── BaseLLMProvider interface (delegated with failover) ──────────────────

    async def generate_response(self, prompt: str) -> str:
        return await self._call_with_failover("generate_response", prompt)

    async def generate_with_messages(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        return await self._call_with_failover(
            "generate_with_messages", messages, system_prompt
        )

    async def generate_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[LLMToolDefinition],
        system_prompt: Optional[str] = None,
        tool_executor: Optional[Callable] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        return await self._call_with_failover(
            "generate_with_tools", messages, tools, system_prompt, tool_executor
        )

    async def generate_json(
        self,
        prompt: str,
        json_schema: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        return await self._call_with_failover("generate_json", prompt, json_schema)

    # ── Passthrough helpers ──────────────────────────────────────────────────

    def _convert_messages_to_native(self, messages: List[LLMMessage]) -> Any:
        return self.primary._convert_messages_to_native(messages)

    def _convert_tools_to_native(self, tools: List[LLMToolDefinition]) -> Any:
        return self.primary._convert_tools_to_native(tools)

    def __repr__(self) -> str:
        return (
            f"LLMRouter("
            f"primary={type(self.primary).__name__}, "
            f"fallback={type(self.fallback).__name__})"
        )
