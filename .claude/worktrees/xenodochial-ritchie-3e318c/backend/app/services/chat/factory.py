"""
Chat Provider Factory - instantiate chat providers by name.
"""
import logging
from typing import Dict, Any, List, Type

from app.services.chat.base_provider import BaseChatProvider
from app.services.chat.telegram_provider import TelegramProvider
from app.services.chat.whatsapp_provider import WhatsAppProvider

logger = logging.getLogger(__name__)


class ChatProviderFactory:
    """Factory for creating chat provider instances."""

    _providers: Dict[str, Type[BaseChatProvider]] = {
        "telegram": TelegramProvider,
        "whatsapp": WhatsAppProvider,
    }

    @classmethod
    def create(cls, provider_name: str, config: Dict[str, Any]) -> BaseChatProvider:
        """
        Create chat provider instance.

        Args:
            provider_name: Name of provider (telegram, whatsapp, etc.)
            config: Provider configuration dict

        Returns:
            BaseChatProvider instance

        Raises:
            ValueError: If provider is not supported
        """
        name = provider_name.lower().strip()
        provider_class = cls._providers.get(name)
        if not provider_class:
            raise ValueError(
                f"Unsupported chat provider: {provider_name}. "
                f"Supported: {list(cls._providers.keys())}"
            )
        return provider_class(config)

    @classmethod
    def register_provider(cls, provider_name: str, provider_class: Type[BaseChatProvider]) -> None:
        """Register a custom chat provider."""
        cls._providers[provider_name.lower()] = provider_class

    @classmethod
    def get_supported_providers(cls) -> List[str]:
        """Return list of supported provider names."""
        return list(cls._providers.keys())
