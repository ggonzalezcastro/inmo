"""
Voice provider factory: registry and get_voice_provider(provider_type, broker_id, db).
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.voice.base_provider import BaseVoiceProvider
from app.services.voice.types import VoiceProviderType

_PROVIDERS: dict = {}


def register_voice_provider(provider_type: VoiceProviderType, provider_class: type) -> None:
    """Register a voice provider implementation."""
    _PROVIDERS[provider_type] = provider_class


async def get_voice_provider(
    provider_type: Optional[str] = None,
    broker_id: Optional[int] = None,
    db: Optional[AsyncSession] = None,
) -> BaseVoiceProvider:
    """
    Return the voice provider for the given type or broker config.
    If broker_id and db are provided, provider is resolved from BrokerVoiceConfig.provider.
    """
    resolved_type = provider_type
    if (broker_id is not None and db is not None) and resolved_type is None:
        from app.services.broker import BrokerVoiceConfigService
        try:
            config = await BrokerVoiceConfigService.get_voice_config(db, broker_id)
            if config and config.get("provider"):
                resolved_type = config["provider"]
        except Exception:
            pass
    if resolved_type is None:
        resolved_type = getattr(settings, "VOICE_PROVIDER", "vapi")
    try:
        ptype = VoiceProviderType(resolved_type)
    except ValueError:
        ptype = VoiceProviderType.VAPI
    provider_class = _PROVIDERS.get(ptype)
    if not provider_class:
        raise ValueError(f"Voice provider '{resolved_type}' not registered")
    return provider_class()


# Register built-in providers
def _register_builtin() -> None:
    from app.services.voice.providers.vapi.provider import VapiProvider
    from app.services.voice.providers.bland.provider import BlandProvider
    register_voice_provider(VoiceProviderType.VAPI, VapiProvider)
    register_voice_provider(VoiceProviderType.BLAND, BlandProvider)


_register_builtin()
