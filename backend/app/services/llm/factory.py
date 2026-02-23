"""
LLM Provider Factory

Factory function to instantiate the correct LLM provider based on configuration.
Supports runtime switching between providers via environment variables and
automatic failover via LLMRouter when LLM_FALLBACK_PROVIDER is configured.
"""
import logging
from typing import Optional
from app.services.llm.base_provider import BaseLLMProvider
from app.config import settings

logger = logging.getLogger(__name__)

# Singleton provider instance (may be an LLMRouter wrapping primary + fallback)
_provider_instance: Optional[BaseLLMProvider] = None


def _build_provider(provider_name: str) -> BaseLLMProvider:
    """Instantiate a concrete provider by name."""
    name = provider_name.lower()

    if name == "gemini":
        from app.services.llm.gemini_provider import GeminiProvider
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
            max_tokens=settings.GEMINI_MAX_TOKENS,
            temperature=settings.GEMINI_TEMPERATURE,
        )

    if name == "claude":
        from app.services.llm.claude_provider import ClaudeProvider
        return ClaudeProvider(
            api_key=getattr(settings, "ANTHROPIC_API_KEY", ""),
            model=getattr(settings, "CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=getattr(settings, "CLAUDE_MAX_TOKENS", 2048),
            temperature=getattr(settings, "CLAUDE_TEMPERATURE", 0.7),
        )

    if name == "openai":
        from app.services.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(
            api_key=getattr(settings, "OPENAI_API_KEY", ""),
            model=getattr(settings, "OPENAI_MODEL", "gpt-4o"),
            max_tokens=getattr(settings, "OPENAI_MAX_TOKENS", 2048),
            temperature=getattr(settings, "OPENAI_TEMPERATURE", 0.7),
        )

    raise ValueError(
        f"Unknown LLM provider: '{provider_name}'. Valid options: gemini, claude, openai"
    )


def get_llm_provider(force_new: bool = False) -> BaseLLMProvider:
    """
    Get the configured LLM provider instance.

    Uses singleton pattern. Set force_new=True to recreate (useful for tests).

    When LLM_FALLBACK_PROVIDER is set (and differs from LLM_PROVIDER),
    returns an LLMRouter that automatically fails over to the secondary provider
    on transient errors (rate limits, timeouts, 5xx responses).

    Provider selection via environment variables:
        LLM_PROVIDER          - primary provider  (default: "gemini")
        LLM_FALLBACK_PROVIDER - secondary provider (default: "claude")

    Returns:
        BaseLLMProvider — either a concrete provider or an LLMRouter.

    Raises:
        ValueError: If an unknown provider name is configured.
    """
    global _provider_instance

    if _provider_instance is not None and not force_new:
        return _provider_instance

    primary_name = getattr(settings, "LLM_PROVIDER", "gemini").lower()
    fallback_name = getattr(settings, "LLM_FALLBACK_PROVIDER", "").lower()

    logger.info(
        "Initializing LLM provider",
        extra={"primary": primary_name, "fallback": fallback_name or "none"},
    )

    primary = _build_provider(primary_name)

    # Wire up the router only when a valid, *different* fallback is configured
    if fallback_name and fallback_name != primary_name:
        try:
            fallback = _build_provider(fallback_name)
            if fallback.is_configured:
                from app.services.llm.router import LLMRouter
                _provider_instance = LLMRouter(primary=primary, fallback=fallback)
                logger.info(
                    "LLMRouter configured",
                    extra={"primary": primary_name, "fallback": fallback_name},
                )
            else:
                logger.warning(
                    "Fallback provider is not configured (missing API key) — router disabled",
                    extra={"fallback": fallback_name},
                )
                _provider_instance = primary
        except Exception as exc:
            logger.warning(
                "Could not build fallback provider — router disabled",
                extra={"fallback": fallback_name, "error": str(exc)},
            )
            _provider_instance = primary
    else:
        _provider_instance = primary

    if primary.is_configured:
        logger.info(
            "LLM provider ready",
            extra={"provider": type(_provider_instance).__name__},
        )
    else:
        logger.warning(
            "Primary LLM provider is not configured (missing API key?)",
            extra={"provider": primary_name},
        )

    return _provider_instance


def reset_provider():
    """Reset the provider singleton (useful for testing)."""
    global _provider_instance
    _provider_instance = None


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def is_gemini() -> bool:
    """Check if primary provider is Gemini."""
    return getattr(settings, "LLM_PROVIDER", "gemini").lower() == "gemini"


def is_claude() -> bool:
    """Check if primary provider is Claude."""
    return getattr(settings, "LLM_PROVIDER", "gemini").lower() == "claude"


def is_openai() -> bool:
    """Check if primary provider is OpenAI."""
    return getattr(settings, "LLM_PROVIDER", "gemini").lower() == "openai"
