"""
LLM Provider Factory

Factory function to instantiate the correct LLM provider based on configuration.
Supports runtime switching between providers via environment variables and
automatic failover via LLMRouter when LLM_FALLBACK_PROVIDER is configured.

Per-agent overrides are resolved via resolve_provider_for_agent(), which reads
per-broker configuration from the database (via Redis cache) and falls back to
the global singleton when no specific config is set.
"""
import logging
from typing import Dict, Optional, Tuple
from app.services.llm.base_provider import BaseLLMProvider
from app.config import settings

logger = logging.getLogger(__name__)

# Singleton provider instance (may be an LLMRouter wrapping primary + fallback)
_provider_instance: Optional[BaseLLMProvider] = None

# Cache of provider instances keyed by full config tuple to avoid re-creating SDK clients
# Key: (provider_name, model, temperature, max_tokens)
_custom_provider_cache: Dict[Tuple, BaseLLMProvider] = {}


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

    if name == "gemma":
        # Gemma runs through the Google Generative AI API (same key as Gemini)
        from app.services.llm.gemini_provider import GeminiProvider
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=getattr(settings, "GEMMA_MODEL", "gemma-4-31b-it"),
            max_tokens=settings.GEMINI_MAX_TOKENS,
            temperature=settings.GEMINI_TEMPERATURE,
        )

    raise ValueError(
        f"Unknown LLM provider: '{provider_name}'. Valid options: gemini, claude, openai, gemma"
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


_fast_provider_instance: Optional[BaseLLMProvider] = None


def get_fast_llm_provider(force_new: bool = False) -> BaseLLMProvider:
    """
    Return a lightweight provider for fast/cheap tasks (e.g. data extraction).

    Uses GEMMA_MODEL (flash-lite) via the Gemini API — same key, much lower latency.
    Falls back to the main provider if Gemma is not configured.
    """
    global _fast_provider_instance
    if _fast_provider_instance is not None and not force_new:
        return _fast_provider_instance

    gemma_model = getattr(settings, "GEMMA_MODEL", "")
    if gemma_model and getattr(settings, "GEMINI_API_KEY", ""):
        try:
            from app.services.llm.gemini_provider import GeminiProvider
            provider = GeminiProvider(
                api_key=settings.GEMINI_API_KEY,
                model=gemma_model,
                max_tokens=1024,
                temperature=0.3,
            )
            if provider.is_configured:
                _fast_provider_instance = provider
                logger.info("Fast LLM provider ready: %s", gemma_model)
                return _fast_provider_instance
        except Exception as exc:
            logger.warning("Could not build fast provider (%s): %s", gemma_model, exc)

    # Fallback: use the main provider
    _fast_provider_instance = get_llm_provider()
    return _fast_provider_instance


def reset_provider():
    """Reset the provider singleton (useful for testing)."""
    global _provider_instance, _fast_provider_instance, _custom_provider_cache
    _provider_instance = None
    _fast_provider_instance = None
    _custom_provider_cache.clear()


# ── Per-agent provider resolution ────────────────────────────────────────────

def _get_provider_defaults(provider_name: str) -> Tuple[float, int]:
    """Return (temperature, max_tokens) defaults for a provider from env/settings."""
    name = provider_name.lower()
    if name == "gemini":
        return (
            float(getattr(settings, "GEMINI_TEMPERATURE", 0.7)),
            int(getattr(settings, "GEMINI_MAX_TOKENS", 1500)),
        )
    if name == "claude":
        return (
            float(getattr(settings, "CLAUDE_TEMPERATURE", 0.7)),
            int(getattr(settings, "CLAUDE_MAX_TOKENS", 2048)),
        )
    if name == "openai":
        return (
            float(getattr(settings, "OPENAI_TEMPERATURE", 0.7)),
            int(getattr(settings, "OPENAI_MAX_TOKENS", 2048)),
        )
    return (0.7, 1500)


def build_provider_from_config(
    provider_name: str,
    model: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> BaseLLMProvider:
    """
    Build a provider with specific settings, wrapping with LLMRouter for
    env-configured fallback if available.

    Instances are cached by full (provider, model, temperature, max_tokens)
    tuple to avoid recreating SDK clients on every request.
    """
    global _custom_provider_cache

    # Resolve effective values — use explicit overrides, fall back to env defaults
    default_temp, default_tokens = _get_provider_defaults(provider_name)
    eff_temperature = temperature if temperature is not None else default_temp
    eff_max_tokens = max_tokens if max_tokens is not None else default_tokens

    cache_key: Tuple = (provider_name, model, eff_temperature, eff_max_tokens)
    if cache_key in _custom_provider_cache:
        return _custom_provider_cache[cache_key]

    name = provider_name.lower()
    if name == "gemini":
        from app.services.llm.gemini_provider import GeminiProvider
        primary = GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=model,
            max_tokens=eff_max_tokens,
            temperature=eff_temperature,
        )
    elif name == "claude":
        from app.services.llm.claude_provider import ClaudeProvider
        primary = ClaudeProvider(
            api_key=getattr(settings, "ANTHROPIC_API_KEY", ""),
            model=model,
            max_tokens=eff_max_tokens,
            temperature=eff_temperature,
        )
    elif name == "openai":
        from app.services.llm.openai_provider import OpenAIProvider
        primary = OpenAIProvider(
            api_key=getattr(settings, "OPENAI_API_KEY", ""),
            model=model,
            max_tokens=eff_max_tokens,
            temperature=eff_temperature,
        )
    else:
        raise ValueError(f"Unknown provider for agent config: '{provider_name}'")

    # Wrap with router using env-configured fallback (same fallback as global provider)
    fallback_name = getattr(settings, "LLM_FALLBACK_PROVIDER", "").lower()
    if fallback_name and fallback_name != name:
        try:
            fallback = _build_provider(fallback_name)
            if fallback.is_configured:
                from app.services.llm.router import LLMRouter
                provider = LLMRouter(primary=primary, fallback=fallback)
            else:
                provider = primary
        except Exception as exc:
            logger.warning("[factory] Could not build fallback for custom provider: %s", exc)
            provider = primary
    else:
        provider = primary

    _custom_provider_cache[cache_key] = provider
    return provider


async def resolve_provider_for_agent(
    agent_type: str,
    broker_id: int,
    db,  # AsyncSession — typed as Any to avoid circular imports
) -> BaseLLMProvider:
    """
    Resolve the effective LLM provider for a specific agent + broker.

    Resolution order:
    1. Per-broker, per-agent config in DB (via Redis cache) — if active
    2. Global provider singleton (env-var configured)

    Falls back to global if:
    - No config exists for this agent/broker
    - Config exists but the provider is not configured (missing API key)
    """
    try:
        from app.services.agents.model_config import get_agent_model_config
        config = await get_agent_model_config(broker_id, agent_type, db)
    except Exception as exc:
        logger.warning(
            "[factory] Could not load agent model config broker=%s agent=%s: %s",
            broker_id, agent_type, exc,
        )
        return get_llm_provider()

    if not config or not config.get("is_active"):
        return get_llm_provider()

    provider_name = config.get("llm_provider", "")
    model = config.get("llm_model", "")
    temperature = config.get("temperature")  # May be None
    max_tokens = config.get("max_tokens")    # May be None

    if not provider_name or not model:
        return get_llm_provider()

    try:
        custom_provider = build_provider_from_config(
            provider_name=provider_name,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # Verify the provider is actually usable (API key configured)
        from app.services.llm.router import LLMRouter
        active = custom_provider.primary if isinstance(custom_provider, LLMRouter) else custom_provider
        if not active.is_configured:
            logger.warning(
                "[factory] Custom provider '%s' for broker=%s agent=%s is not configured "
                "(missing API key) — falling back to global",
                provider_name, broker_id, agent_type,
            )
            return get_llm_provider()

        return custom_provider

    except Exception as exc:
        logger.warning(
            "[factory] Failed to build custom provider for broker=%s agent=%s: %s — falling back",
            broker_id, agent_type, exc,
        )
        return get_llm_provider()


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
