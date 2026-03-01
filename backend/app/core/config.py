from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional
import os


class Settings(BaseSettings):
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
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    # 1500 tokens: system prompt (~400t) + history (~600t) + response (~500t).
    # Previous value of 600 caused silent truncation mid-sentence.
    GEMINI_MAX_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", "1500"))
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))

    # Anthropic Claude
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    # 2048 tokens: same reasoning as Gemini — context + response headroom.
    CLAUDE_MAX_TOKENS: int = int(os.getenv("CLAUDE_MAX_TOKENS", "2048"))
    CLAUDE_TEMPERATURE: float = float(os.getenv("CLAUDE_TEMPERATURE", "0.7"))

    # OpenAI GPT
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "2048"))
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

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

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Google Calendar API
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REFRESH_TOKEN: str = os.getenv("GOOGLE_REFRESH_TOKEN", "")
    GOOGLE_CALENDAR_ID: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    GOOGLE_CREDENTIALS_PATH: Optional[str] = os.getenv("GOOGLE_CREDENTIALS_PATH", None)

    # Voice provider selection (vapi, bland, retell, etc.)
    VOICE_PROVIDER: str = os.getenv("VOICE_PROVIDER", "vapi")

    # Vapi.ai - AI Voice Agents (assistant_id per broker in BrokerVoiceConfig; fallback below)
    VAPI_API_KEY: str = os.getenv("VAPI_API_KEY", "")
    VAPI_PHONE_NUMBER_ID: str = os.getenv("VAPI_PHONE_NUMBER_ID", "")
    VAPI_ASSISTANT_ID: str = os.getenv("VAPI_ASSISTANT_ID", "")
    # Secret for verifying Vapi webhook signatures (x-vapi-secret header).
    # Configure in Vapi dashboard → Assistant → Server URL → Secret.
    # If empty, verification is skipped (dev mode only — MUST be set in production).
    VAPI_WEBHOOK_SECRET: str = os.getenv("VAPI_WEBHOOK_SECRET", "")
    WEBHOOK_BASE_URL: str = os.getenv("WEBHOOK_BASE_URL", "http://localhost:8000")

    # Other voice providers (for future use)
    BLAND_API_KEY: str = os.getenv("BLAND_API_KEY", "")
    RETELL_API_KEY: str = os.getenv("RETELL_API_KEY", "")

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

    # Environment
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # CORS - Comma separated list of allowed origins
    ALLOWED_ORIGINS: str = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    )

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env that aren't in the model

    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v, info):
        """Validate SECRET_KEY is secure in production"""
        import warnings
        env = os.getenv("ENVIRONMENT", "development")

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
