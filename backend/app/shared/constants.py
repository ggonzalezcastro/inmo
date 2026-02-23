"""Shared constants and cache key patterns."""


class CacheKeys:
    """Standard cache key patterns (use .format() for placeholders)."""
    BROKER_CONFIG = "broker_config:{broker_id}"
    LEAD_CONTEXT = "lead_context:{lead_id}"
    VOICE_CONFIG = "voice_config:{broker_id}"
