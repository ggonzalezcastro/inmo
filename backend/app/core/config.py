from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional
import os


class Settings(BaseSettings):
    # backend/.env primero; ../.env (raíz del repo) sobrescribe — útil si editás .env en la raíz
    # y corrés uvicorn desde backend/
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/lead_agent"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT & Security - NO default value for security
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # LLM Provider Selection (gemini, claude, openai)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
    # Fallback provider when primary fails (used by LLMRouter)
    LLM_FALLBACK_PROVIDER: str = os.getenv("LLM_FALLBACK_PROVIDER", "claude")

    # Google Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    # 1500 tokens: system prompt (~400t) + history (~600t) + response (~500t).
    # Previous value of 600 caused silent truncation mid-sentence.
    GEMINI_MAX_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", "1500"))
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))

    GEMINI_THINKING_BUDGET: int = int(os.getenv("GEMINI_THINKING_BUDGET", "1024"))
    # -1 = dynamic (model decides when to think)
    #  0 = disabled (no thinking, compatible with all models)
    # >0 = fixed token budget for thinking (1024 = default, enough for most reasoning)


    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_BASE_URL: str = os.getenv("ANTHROPIC_BASE_URL", "")  # override for compatible APIs (MiniMax, etc.)
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    # 2048 tokens: same reasoning as Gemini — context + response headroom.
    CLAUDE_MAX_TOKENS: int = int(os.getenv("CLAUDE_MAX_TOKENS", "2048"))
    CLAUDE_TEMPERATURE: float = float(os.getenv("CLAUDE_TEMPERATURE", "0.7"))

    # OpenAI GPT
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "2048"))
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")  # override for OpenAI-compatible APIs (MiniMax, etc.)

    # OpenRouter (OpenAI-compatible, routes to any model)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")
    OPENROUTER_MAX_TOKENS: int = int(os.getenv("OPENROUTER_MAX_TOKENS", "2048"))
    OPENROUTER_TEMPERATURE: float = float(os.getenv("OPENROUTER_TEMPERATURE", "0.7"))

    # MCP Server transport: "http" (recommended for production) or "stdio" (dev fallback)
    MCP_TRANSPORT: str = os.getenv("MCP_TRANSPORT", "http")
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8001")
    MCP_SERVER_PORT: int = int(os.getenv("MCP_SERVER_PORT", "8001"))

    # LLM temperatures per call type.
    # Lower = more deterministic/precise. Higher = more creative/natural.
    # qualify: extract financial data (DICOM, salary) — precision over creativity
    # chat:    conversational replies — balanced
    # json:    structured output — maximum consistency
    LLM_TEMPERATURE_QUALIFY: float = float(os.getenv("LLM_TEMPERATURE_QUALIFY", "0.3"))
    LLM_TEMPERATURE_CHAT: float = float(os.getenv("LLM_TEMPERATURE_CHAT", "0.7"))
    LLM_TEMPERATURE_JSON: float = float(os.getenv("LLM_TEMPERATURE_JSON", "0.1"))

    # Telegram
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    TELEGRAM_WEBHOOK_URL: str = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    TELEGRAM_WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")

    # WhatsApp / Meta Cloud API
    WHATSAPP_ACCESS_TOKEN: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    WHATSAPP_WEBHOOK_SECRET: str = os.getenv("WHATSAPP_WEBHOOK_SECRET", "")

    # Meta platform (multi-tenant WhatsApp, Instagram, Messenger and Ads)
    META_APP_ID: str = os.getenv("META_APP_ID", "")
    META_APP_SECRET: str = os.getenv("META_APP_SECRET", "")
    # Instagram Login has its own application identifier and secret in Meta.
    # They are distinct from the parent Meta Business App credentials.
    META_INSTAGRAM_APP_ID: str = os.getenv("META_INSTAGRAM_APP_ID", "")
    META_INSTAGRAM_APP_SECRET: str = os.getenv("META_INSTAGRAM_APP_SECRET", "")
    META_GRAPH_API_VERSION: str = os.getenv("META_GRAPH_API_VERSION", "v26.0")
    META_WEBHOOK_VERIFY_TOKEN: str = os.getenv(
        "META_WEBHOOK_VERIFY_TOKEN", WHATSAPP_VERIFY_TOKEN
    )
    META_OAUTH_REDIRECT_BASE_URL: str = os.getenv(
        "META_OAUTH_REDIRECT_BASE_URL", "http://localhost:8000/api/v1/meta"
    )
    META_WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID: str = os.getenv(
        "META_WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID", ""
    )
    META_CREDENTIAL_ENCRYPTION_KEY: str = os.getenv(
        "META_CREDENTIAL_ENCRYPTION_KEY", ""
    )
    META_RAW_WEBHOOK_RETENTION_DAYS: int = int(
        os.getenv("META_RAW_WEBHOOK_RETENTION_DAYS", "7")
    )
    META_FEATURE_ENABLED: bool = os.getenv(
        "META_FEATURE_ENABLED", "false"
    ).lower() == "true"
    META_BROKER_DEFAULT_ENABLED: bool = os.getenv(
        "META_BROKER_DEFAULT_ENABLED", "false"
    ).lower() == "true"
    META_WHATSAPP_ASSET_ROUTING_ENABLED: bool = os.getenv(
        "META_WHATSAPP_ASSET_ROUTING_ENABLED", "false"
    ).lower() == "true"
    # Temporary rollback path during the Meta canary. Keep enabled until task
    # 12.9 proves zero legacy reads through two stable releases.
    META_WHATSAPP_LEGACY_FALLBACK_ENABLED: bool = os.getenv(
        "META_WHATSAPP_LEGACY_FALLBACK_ENABLED", "true"
    ).lower() == "true"
    META_INSTAGRAM_ENABLED: bool = os.getenv(
        "META_INSTAGRAM_ENABLED", "false"
    ).lower() == "true"
    META_MESSENGER_ENABLED: bool = os.getenv(
        "META_MESSENGER_ENABLED", "false"
    ).lower() == "true"
    META_ADS_ENABLED: bool = os.getenv(
        "META_ADS_ENABLED", "false"
    ).lower() == "true"
    META_LEAD_ADS_ENABLED: bool = os.getenv(
        "META_LEAD_ADS_ENABLED", "false"
    ).lower() == "true"
    META_CONVERSIONS_API_ENABLED: bool = os.getenv(
        "META_CONVERSIONS_API_ENABLED", "false"
    ).lower() == "true"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Google Calendar API
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REFRESH_TOKEN: str = os.getenv("GOOGLE_REFRESH_TOKEN", "")
    GOOGLE_CALENDAR_ID: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    GOOGLE_CREDENTIALS_PATH: Optional[str] = os.getenv("GOOGLE_CREDENTIALS_PATH", None)
    # OAuth callback — must be registered in Google Cloud Console as authorized redirect URI
    # Example: https://yourdomain.com/broker/calendar/callback
    GOOGLE_OAUTH_REDIRECT_URI: str = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/api/broker/calendar/callback")
    # Frontend URL — used to redirect after OAuth flow completes
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    # Base path the SPA is served under (e.g. "/app"); used to build post-payment
    # redirects. Empty = served at root.
    FRONTEND_BASE_PATH: str = os.getenv("FRONTEND_BASE_PATH", "")

    # Microsoft Outlook Calendar (Azure App Registration)
    MICROSOFT_CLIENT_ID: str = os.getenv("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET: str = os.getenv("MICROSOFT_CLIENT_SECRET", "")
    # "common" supports both personal (MSA) and work/school (AAD) accounts
    MICROSOFT_TENANT_ID: str = os.getenv("MICROSOFT_TENANT_ID", "common")
    MICROSOFT_OAUTH_REDIRECT_URI: str = os.getenv(
        "MICROSOFT_OAUTH_REDIRECT_URI",
        "http://localhost:8000/api/broker/calendar/outlook/callback",
    )

    # Voice provider selection (vapi, bland, retell, etc.)
    VOICE_PROVIDER: str = os.getenv("VOICE_PROVIDER", "vapi")

    # Vapi.ai - AI Voice Agents (assistant_id per broker in BrokerVoiceConfig; fallback below)
    VAPI_API_KEY: str = os.getenv("VAPI_API_KEY", "")
    VAPI_PHONE_NUMBER_ID: str = os.getenv("VAPI_PHONE_NUMBER_ID", "")
    VAPI_ASSISTANT_ID: str = os.getenv("VAPI_ASSISTANT_ID", "")
    # Public key for @vapi-ai/web SDK (browser-safe, read-only — starts calls only).
    # Found in VAPI dashboard → API Keys → Public Key.
    VAPI_PUBLIC_KEY: str = os.getenv("VAPI_PUBLIC_KEY", "")
    # Secret for verifying Vapi webhook signatures (x-vapi-secret header).
    # Configure in Vapi dashboard → Assistant → Server URL → Secret.
    # If empty, verification is skipped (dev mode only — MUST be set in production).
    VAPI_WEBHOOK_SECRET: str = os.getenv("VAPI_WEBHOOK_SECRET", "")
    WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "http://localhost:8000")

    # Other voice providers (for future use)
    BLAND_API_KEY: str = os.getenv("BLAND_API_KEY", "")
    RETELL_API_KEY: str = os.getenv("RETELL_API_KEY", "")

    # ── Transbank Webpay Plus ───────────────────────────────────────────────
    # Per-broker credentials live in broker_payment_configs (see BrokerPaymentConfig).
    # These are ONLY the shared INTEGRATION (test) fallback used when a broker has
    # not configured its own credentials. They are Transbank's public integration
    # credentials — NOT production. Phase 1: every broker runs against integration.
    TRANSBANK_DEFAULT_COMMERCE_CODE: str = os.getenv(
        "TRANSBANK_DEFAULT_COMMERCE_CODE", "597055555532"
    )
    TRANSBANK_DEFAULT_API_KEY: str = os.getenv(
        "TRANSBANK_DEFAULT_API_KEY",
        "579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C",
    )
    # Phase 1 kill-switch: force all brokers to integration regardless of their
    # per-broker environment setting. Flip to "false" in phase 2 to allow production.
    TRANSBANK_FORCE_INTEGRATION: bool = (
        os.getenv("TRANSBANK_FORCE_INTEGRATION", "true").lower() == "true"
    )

    # ── Pipecat voice stack (autonomous / handoff / copilot / coaching) ─────
    # TTS provider: "elevenlabs" (lowest latency w/ flash v2.5) | "deepgram" | "fish_audio"
    TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "elevenlabs")
    # ElevenLabs
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "")
    # eleven_flash_v2_5 = ~75ms TTFB (vs ~200ms multilingual_v2). 32 languages.
    ELEVENLABS_MODEL: str = os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5")
    # Deepgram (STT + optional TTS)
    DEEPGRAM_API_KEY: str = os.getenv("DEEPGRAM_API_KEY", "")
    DEEPGRAM_TTS_VOICE: str = os.getenv("DEEPGRAM_TTS_VOICE", "aura-2-thalia-en")
    # Fish Audio (legacy / Spanish premium voices)
    FISH_AUDIO_API_KEY: str = os.getenv("FISH_AUDIO_API_KEY", "")
    FISH_AUDIO_VOICE_ID: str = os.getenv("FISH_AUDIO_VOICE_ID", "")
    FISH_AUDIO_MODEL: str = os.getenv("FISH_AUDIO_MODEL", "s2-pro")
    # Twilio (telephony transport for Pipecat WS)
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    TWILIO_SIP_DOMAIN: str = os.getenv("TWILIO_SIP_DOMAIN", "")

    # Gemini Context Caching (TASK-028)
    # Caches static broker system prompts — reduces token costs ~75%.
    # Requires prompt > ~4096 tokens; off by default until prompt grows with RAG.
    GEMINI_CONTEXT_CACHING_ENABLED: bool = os.getenv("GEMINI_CONTEXT_CACHING_ENABLED", "false").lower() == "true"
    GEMINI_CONTEXT_CACHE_TTL: int = int(os.getenv("GEMINI_CONTEXT_CACHE_TTL", "3600"))  # 1 hour

    # Semantic cache
    SEMANTIC_CACHE_ENABLED: bool = os.getenv("SEMANTIC_CACHE_ENABLED", "true").lower() == "true"
    SEMANTIC_CACHE_THRESHOLD: float = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.92"))
    SEMANTIC_CACHE_TTL: int = int(os.getenv("SEMANTIC_CACHE_TTL", "3600"))    # 1 hour
    SEMANTIC_CACHE_MAX_ENTRIES: int = int(os.getenv("SEMANTIC_CACHE_MAX_ENTRIES", "500"))

    # Human mode timeout (tiered escalation when agent goes AFK)
    HUMAN_MODE_REMINDER_MINUTES: int = int(os.getenv("HUMAN_MODE_REMINDER_MINUTES", "15"))
    HUMAN_MODE_ADMIN_ALERT_MINUTES: int = int(os.getenv("HUMAN_MODE_ADMIN_ALERT_MINUTES", "30"))
    HUMAN_MODE_AUTO_RELEASE_MINUTES: int = int(os.getenv("HUMAN_MODE_AUTO_RELEASE_MINUTES", "60"))

    # Sentiment Analysis (frustration detection + auto-escalation)
    SENTIMENT_ANALYSIS_ENABLED: bool = os.getenv("SENTIMENT_ANALYSIS_ENABLED", "true").lower() == "true"
    SENTIMENT_TONE_THRESHOLD: float = float(os.getenv("SENTIMENT_TONE_THRESHOLD", "0.4"))
    SENTIMENT_ESCALATE_THRESHOLD: float = float(os.getenv("SENTIMENT_ESCALATE_THRESHOLD", "0.7"))
    SENTIMENT_HISTORY_WINDOW: int = int(os.getenv("SENTIMENT_HISTORY_WINDOW", "3"))
    # Min heuristic confidence to skip LLM call (sarcasm always calls LLM regardless)
    SENTIMENT_LLM_CONFIRM_THRESHOLD: float = float(os.getenv("SENTIMENT_LLM_CONFIRM_THRESHOLD", "0.60"))

    # Sentry error monitoring
    # SENTRY_DSN: get it from sentry.io → Project → Settings → Client Keys
    # SENTRY_AUTH_TOKEN: sentry.io → User Settings → API Tokens (scope: project:read)
    # SENTRY_ORG: your Sentry organization slug (e.g. "my-company")
    # SENTRY_PROJECT: your Sentry project slug (e.g. "inmo-backend")
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    SENTRY_AUTH_TOKEN: str = os.getenv("SENTRY_AUTH_TOKEN", "")
    SENTRY_ORG: str = os.getenv("SENTRY_ORG", "")
    SENTRY_PROJECT: str = os.getenv("SENTRY_PROJECT", "")

    # Storage
    STORAGE_DRIVER: str = os.getenv("STORAGE_DRIVER", "local")
    STORAGE_VOLUME_PATH: str = os.getenv("STORAGE_VOLUME_PATH", "/data/deals")
    STORAGE_LOCAL_PATH: str = os.getenv("STORAGE_LOCAL_PATH", "./.local-storage")
    STORAGE_SIGNING_SECRET: str = os.getenv("STORAGE_SIGNING_SECRET", "")
    STORAGE_PRESIGN_TTL_SEC: int = int(os.getenv("STORAGE_PRESIGN_TTL_SEC", "600"))
    STORAGE_MAX_FILE_MB: int = int(os.getenv("STORAGE_MAX_FILE_MB", "15"))

    # Environment
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # CORS - Comma separated list of allowed origins
    ALLOWED_ORIGINS: str = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    )

    @field_validator('DATABASE_URL', mode='before')
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        """Render (and some other platforms) provide postgres:// URLs.
        SQLAlchemy async requires postgresql+asyncpg://."""
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v, info):
        """Validate SECRET_KEY is secure in production"""
        import warnings
        env = os.getenv("ENVIRONMENT", "development")

        # Known dev/placeholder keys that have appeared in repo files — never valid in prod
        _KNOWN_WEAK_KEYS = {
            "dev-secret-key",
            "dev-only-secret-key-not-for-production!",
            "your-super-secret-key-min-32-chars",
        }
        if env == "production" and v in _KNOWN_WEAK_KEYS:
            raise ValueError(
                "SECRET_KEY is a known development placeholder. "
                "Generate a real key: openssl rand -hex 32"
            )

        if not v or len(v) < 32:
            if env == "production":
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters in production. "
                    "Set SECRET_KEY environment variable with a secure random string."
                )
            else:
                warnings.warn(
                    "SECRET_KEY is not set or too short. "
                    "This is acceptable in development but MUST be set in production.",
                    UserWarning
                )
                # Provide a development-only fallback
                return v if v else "dev-only-secret-key-not-for-production!"
        return v


settings = Settings()
