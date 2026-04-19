# Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@db:5432/lead_agent

# Redis
REDIS_URL=redis://redis:6379/0

# JWT & Security
SECRET_KEY=your-secret-key-here-min-32-chars-please
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-3.5-turbo

# Telegram
TELEGRAM_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/webhooks/telegram
TELEGRAM_WEBHOOK_SECRET=your-webhook-secret

# Environment
DEBUG=False
ENVIRONMENT=development

# Database Pool
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# Celery
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Google Calendar API (para generar URLs reales de Google Meet)
# Opción 1: Service Account (recomendado para producción)
GOOGLE_CREDENTIALS_PATH=/path/to/service-account-credentials.json

# Opción 2: OAuth2 (para desarrollo)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REFRESH_TOKEN=your-refresh-token
GOOGLE_CALENDAR_ID=primary  # o el ID de tu calendario específico
```

