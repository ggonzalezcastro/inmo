"""Abstract base class for voice providers."""
from abc import ABC, abstractmethod

from app.services.voice.types import (
    MakeCallRequest,
    CallStatusResult,
    WebhookEvent,
    VoiceProviderType,
)


class BaseVoiceProvider(ABC):
    """Contract for any voice provider (VAPI, Bland, Retell, etc.)."""

    @abstractmethod
    async def make_call(self, request: MakeCallRequest) -> str:
        """Start an outbound call. Returns external_call_id."""

    @abstractmethod
    async def get_call_status(self, external_call_id: str) -> CallStatusResult:
        """Get status of an active or completed call."""

    @abstractmethod
    async def handle_webhook(self, payload: dict, headers: dict = None) -> WebhookEvent:
        """Parse provider webhook payload and return normalized event."""

    @abstractmethod
    async def cancel_call(self, external_call_id: str) -> bool:
        """Cancel an active call. Returns True if cancelled."""

    @abstractmethod
    def get_provider_type(self) -> VoiceProviderType:
        """Return the provider type."""

    async def validate_config(self) -> bool:
        """Validate that the provider configuration is correct."""
        return True
