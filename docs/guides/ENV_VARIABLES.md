# Variables de Entorno

> Última actualización: 2026-04-18

## Referencia Completa

Todas las variables de entorno usadas en el proyecto. Organizadas por categoría.

---

## Base de Datos

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Sí | - | Connection string de PostgreSQL. Formato: `postgresql+asyncpg://user:pass@host:5432/db` |
| `SECRET_KEY` | Sí | - | Clave secreta para JWT y encriptación. Mínimo 32 caracteres. |

**Ejemplo:**
```bash
DATABASE_URL=postgresql+asyncpg://lead_user:lead_pass_123@db:5432/lead_agent
SECRET_KEY=your-super-secret-key-change-in-production-minimum-32-chars
```

---

## Redis / Celery

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `REDIS_URL` | Sí | `redis://localhost:6379/0` | URL de Redis para cache |
| `CELERY_BROKER_URL` | Sí | `redis://localhost:6379/1` | Broker de Celery |
| `CELERY_RESULT_BACKEND` | Sí | `redis://localhost:6379/2` | Backend de resultados de Celery |

**Ejemplo:**
```bash
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
```

---

## LLM Providers

### Configuración General

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | No | `gemini` | Provider primario: `gemini`, `claude`, `openai` |
| `LLM_FALLBACK_PROVIDER` | No | - | Provider fallback cuando el primario falla |

### Google Gemini

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Sí* | - | API key de Google AI Studio |
| `GEMINI_MODEL` | No | `gemini-2.0-flash-lite` | Modelo a usar |
| `GEMINI_MAX_TOKENS` | No | `2048` | Máximo de tokens en respuesta |
| `GEMINI_TEMPERATURE` | No | `0.7` | Temperatura (0.0-1.0) |
| `GEMINI_THINKING_BUDGET` | No | `0` | Budget de thinking para Gemini 2.5. 0=off, -1=dynamic |

**Ejemplo:**
```bash
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.0-flash
GEMINI_MAX_TOKENS=2048
GEMINI_TEMPERATURE=0.7
```

### Anthropic Claude

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Sí* | - | API key de Anthropic |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-20250514` | Modelo a usar |

*Requerido solo si usas Claude como provider.

### OpenAI

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Sí* | - | API key de OpenAI |
| `OPENAI_MODEL` | No | `gpt-4o` | Modelo a usar |

*Requerido solo si usas OpenAI como provider.

---

## Telegram

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `TELEGRAM_TOKEN` | Sí* | - | Token del bot de Telegram |
| `TELEGRAM_WEBHOOK_URL` | No | - | URL del webhook en producción |
| `TELEGRAM_WEBHOOK_SECRET` | No | - | Secreto para verificar webhook |

*Requerido solo si usas Telegram.

**Ejemplo:**
```bash
TELEGRAM_TOKEN=123456:ABC-DEF
TELEGRAM_WEBHOOK_URL=https://tu-dominio.com/api/webhooks/telegram
TELEGRAM_WEBHOOK_SECRET=my-secret-token
```

---

## WhatsApp

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `WHATSAPP_ACCESS_TOKEN` | Sí* | - | Access token de Meta Graph API |
| `WHATSAPP_PHONE_NUMBER_ID` | Sí* | - | Phone Number ID del WhatsApp Business |
| `WHATSAPP_VERIFY_TOKEN` | Sí* | - | Token para verificar webhook |
| `WHATSAPP_WEBHOOK_SECRET` | No | - | Secreto del webhook |

*Requerido solo si usas WhatsApp.

**Ejemplo:**
```bash
WHATSAPP_ACCESS_TOKEN=EAAXXXX...
WHATSAPP_PHONE_NUMBER_ID=123456789
WHATSAPP_VERIFY_TOKEN=my-verify-token
```

---

## MCP Server

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `MCP_TRANSPORT` | No | `stdio` | Transporte: `http` o `stdio` |
| `MCP_SERVER_URL` | No | `http://mcp-server:8001` | URL del servidor MCP |

**Ejemplo:**
```bash
MCP_TRANSPORT=http
MCP_SERVER_URL=http://mcp-server:8001
```

---

## Calendar - Google

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `GOOGLE_CLIENT_ID` | Sí* | - | Client ID de Google OAuth |
| `GOOGLE_CLIENT_SECRET` | Sí* | - | Client Secret de Google OAuth |
| `GOOGLE_REFRESH_TOKEN` | Sí* | - | Refresh token (obtenido via OAuth flow) |
| `GOOGLE_CALENDAR_ID` | No | `primary` | ID del calendario de Google |
| `GOOGLE_OAUTH_REDIRECT_URI` | No | `http://localhost:8000/api/broker/calendar/callback` | OAuth callback URI |

*Requerido solo si usas Google Calendar.

---

## Calendar - Microsoft Outlook

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `MICROSOFT_CLIENT_ID` | Sí* | - | Application ID de Azure AD |
| `MICROSOFT_CLIENT_SECRET` | Sí* | - | Client Secret |
| `MICROSOFT_TENANT_ID` | No | `common` | Tenant ID de Azure AD |
| `MICROSOFT_OAUTH_REDIRECT_URI` | Sí* | - | OAuth callback URI |

*Requerido solo si usas Outlook Calendar.

---

## VAPI (Voice)

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `VAPI_API_KEY` | Sí* | - | API Key de VAPI |
| `VAPI_PRIVATE_KEY` | No | - | Private Key (opcional) |
| `VAPI_PHONE_NUMBER_ID` | No | - | Phone Number ID para llamadas entrantes |

*Requerido solo si usas VAPI.

---

## Frontend

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `VITE_API_URL` | No | `http://localhost:8000` | URL base del API backend |
| `FRONTEND_URL` | No | `http://localhost:5173` | URL pública del frontend |

**Ejemplo:**
```bash
VITE_API_URL=http://localhost:8000
FRONTEND_URL=http://localhost:5173
```

---

## Observabilidad

### OpenTelemetry

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `OTEL_ENABLED` | No | `false` | Habilitar tracing con OTEL |
| `OTEL_SERVICE_NAME` | No | `inmo-backend` | Nombre del servicio |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | `http://localhost:4318` | Endpoint del OTEL collector |

### Sentry

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `SENTRY_DSN` | No | - | DSN de Sentry para error tracking |

---

## Feature Flags

| Variable | Required | Default | Descripción |
|----------|----------|---------|-------------|
| `SEMANTIC_CACHE_ENABLED` | No | `true` | Habilitar cache semántico en Redis |
| `SENTIMENT_ANALYSIS_ENABLED` | No | `true` | Habilitar análisis de sentimiento |
| `DAILY_COST_ALERT_USD` | No | `10.0` | Alert threshold para costos diarios (USD) |

---

## Archivo .env de ejemplo

```bash
# ===================
# DATABASE
# ===================
DATABASE_URL=postgresql+asyncpg://lead_user:lead_pass_123@localhost:5432/lead_agent
SECRET_KEY=change-this-to-a-secure-random-string-minimum-32-chars

# ===================
# REDIS
# ===================
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# ===================
# LLM PROVIDERS
# ===================
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash-lite
GEMINI_MAX_TOKENS=2048
GEMINI_TEMPERATURE=0.7

# ===================
# TELEGRAM (opcional)
# ===================
TELEGRAM_TOKEN=your_telegram_bot_token

# ===================
# WHATSAPP (opcional)
# ===================
WHATSAPP_ACCESS_TOKEN=your_whatsapp_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_VERIFY_TOKEN=your_verify_token

# ===================
# FRONTEND
# ===================
FRONTEND_URL=http://localhost:5173

# ===================
# OBSERVABILITY
# ===================
OTEL_ENABLED=false
OTEL_SERVICE_NAME=inmo-backend
```

---

## Changelog

| Fecha | Descripción |
|--------|-------------|
| 2026-04-18 | Creación del documento con todas las variables |
| 2026-04-17 | Agregadas secciones de MCP y Feature Flags |
