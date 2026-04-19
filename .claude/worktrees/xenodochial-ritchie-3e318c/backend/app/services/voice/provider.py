"""
Voice provider entry point. Re-exports VapiProvider and get_voice_provider.
For backward compatibility, get_voice_provider() returns a provider that accepts
both MakeCallRequest and the legacy make_call(phone=, webhook_url=, context=).
"""
from app.services.voice.providers.vapi.provider import VapiProvider
from app.services.voice.types import MakeCallRequest


class _VapiProviderCompat(VapiProvider):
    """Accepts legacy make_call(phone=, webhook_url=, context=) until call_service is refactored."""

    async def make_call(
        self,
        request: MakeCallRequest = None,
        *,
        phone: str = None,
        webhook_url: str = None,
        context: dict = None,
        from_number: str = None,
    ) -> str:
        if request is not None and phone is None and context is None:
            return await super().make_call(request)
        ctx = context or {}
        req = MakeCallRequest(
            phone_number=phone,
            broker_id=ctx.get("broker_id") or 0,
            lead_id=ctx.get("lead_id"),
            agent_type=ctx.get("agent_type"),
            webhook_url=webhook_url or "",
            metadata={
                "db": ctx.get("db"),
                "webhook_url": webhook_url,
                "voice_call_id": ctx.get("voice_call_id"),
                "campaign_id": ctx.get("campaign_id"),
            },
        )
        return await super().make_call(req)


def get_voice_provider() -> VapiProvider:
    """Return the default voice provider (VAPI with backward-compat signature)."""
    return _VapiProviderCompat()
