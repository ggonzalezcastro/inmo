---
title: Guía de Despliegue
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# Guía de Despliegue

## Arquitectura de Despliegue

```mermaid
flowchart TB
    subgraph cloud [Cloud Provider]
        subgraph app [Application]
            BE[Backend - FastAPI]
            FE[Frontend - React]
            WK[Celery Worker]
            BT[Celery Beat]
        end
        subgraph data [Data Layer]
            PG[(PostgreSQL)]
            RD[(Redis)]
        end
    end
    subgraph external [Servicios Externos]
        LLM[LLM APIs]
        VAPI_SVC[VAPI.ai]
        GCAL[Google Calendar]
        TGAPI[Telegram API]
    end

    BE --> PG
    BE --> RD
    WK --> PG
    WK --> RD
    BT --> RD
    FE --> BE
    BE --> LLM
    BE --> VAPI_SVC
    BE --> GCAL
    BE --> TGAPI
```

## Docker Compose (Producción)

El proyecto incluye un `docker-compose.yml` listo para producción:

```bash
# Build e iniciar
docker-compose up -d --build

# Ver logs
docker-compose logs -f backend

# Reiniciar un servicio
docker-compose restart backend
```

### Servicios

| Servicio | Imagen | Puerto | Descripción |
|----------|--------|--------|-------------|
| `db` | postgres:15 | 5432 | Base de datos |
| `redis` | redis:7 | 6379 | Cache y broker |
| `backend` | Custom | 8000 | API FastAPI |
| `celery` | Custom | - | Worker de tareas |
| `celery-beat` | Custom | - | Scheduler |

## Variables de Entorno de Producción

### Requeridas

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | `redis://host:6379/0` |
| `SECRET_KEY` | JWT secret, mínimo 32 caracteres |
| `ENVIRONMENT` | `production` |
| `ALLOWED_ORIGINS` | URLs del frontend, separadas por coma |

### LLM (al menos uno)

| Variable | Descripción |
|----------|-------------|
| `LLM_PROVIDER` | `gemini`, `claude`, o `openai` |
| `GEMINI_API_KEY` | API key de Google Gemini |
| `ANTHROPIC_API_KEY` | API key de Anthropic |
| `OPENAI_API_KEY` | API key de OpenAI |

### Voz (opcional)

| Variable | Descripción |
|----------|-------------|
| `VOICE_PROVIDER` | `vapi` o `bland` |
| `VAPI_API_KEY` | API key de VAPI |
| `VAPI_PHONE_NUMBER_ID` | Phone number de VAPI |
| `BLAND_API_KEY` | API key de Bland AI |
| `WEBHOOK_BASE_URL` | URL pública del backend |

### Telegram (opcional)

| Variable | Descripción |
|----------|-------------|
| `TELEGRAM_TOKEN` | Token del bot |
| `TELEGRAM_WEBHOOK_URL` | URL pública para webhook |
| `TELEGRAM_WEBHOOK_SECRET` | Secret de verificación |

### Google Calendar (opcional)

| Variable | Descripción |
|----------|-------------|
| `GOOGLE_CLIENT_ID` | OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | OAuth Client Secret |
| `GOOGLE_REFRESH_TOKEN` | Refresh token |
| `GOOGLE_CALENDAR_ID` | Calendar ID (default: `primary`) |

## Checklist de Despliegue

### Pre-despliegue

- [ ] Variables de entorno configuradas
- [ ] `SECRET_KEY` de al menos 32 caracteres
- [ ] `ENVIRONMENT=production`
- [ ] `ALLOWED_ORIGINS` configurado con dominio del frontend
- [ ] Base de datos PostgreSQL provisionada
- [ ] Redis provisionado
- [ ] SSL/TLS configurado

### Post-despliegue

- [ ] `GET /health` retorna `{"status": "healthy"}`
- [ ] Migraciones ejecutadas (`alembic upgrade head`)
- [ ] Superadmin creado
- [ ] Frontend accesible
- [ ] Webhooks configurados (Telegram, Voz)
- [ ] Rate limiting activo (solo en producción)
- [ ] CORS permitiendo solo orígenes necesarios

## Opciones de Despliegue

### Railway

[TODO: Instrucciones específicas para Railway]

### Vercel (Frontend)

[TODO: Instrucciones específicas para Vercel]

### VPS / Servidor Propio

```bash
# Clonar repositorio
git clone <repo-url>
cd inmo

# Configurar variables de entorno
cp .env.example .env
vim .env

# Docker Compose
docker-compose -f docker-compose.yml up -d

# Verificar
curl https://tu-dominio.com/health
```

## Monitoreo

### Health Check

```bash
# Verificar salud del sistema
curl https://tu-dominio.com/health
```

### Logs

```bash
# Backend
docker-compose logs -f backend

# Celery worker
docker-compose logs -f celery

# Todos los servicios
docker-compose logs -f
```

### Base de Datos

```bash
# Conectar a PostgreSQL
docker-compose exec db psql -U postgres -d lead_agent

# Verificar tablas
\dt

# Contar leads
SELECT COUNT(*) FROM leads;
```

## Backup

### Base de Datos

```bash
# Backup
docker-compose exec db pg_dump -U postgres lead_agent > backup_$(date +%Y%m%d).sql

# Restore
docker-compose exec -T db psql -U postgres lead_agent < backup_20260221.sql
```

### Redis

Redis se usa solo para cache y colas, los datos críticos están en PostgreSQL. No requiere backup independiente.
