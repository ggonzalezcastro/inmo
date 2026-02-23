---
title: Guía de Inicio
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# Guía de Inicio

## Prerrequisitos

| Software | Versión Mínima | Descripción |
|----------|---------------|-------------|
| Python | 3.11+ | Runtime del backend |
| Node.js | 18+ | Runtime del frontend |
| PostgreSQL | 15 | Base de datos |
| Redis | 7+ | Cache y cola de tareas |
| Docker + Docker Compose | 24+ | Contenedores (opcional) |

## Instalación Rápida con Docker

```bash
git clone <repo-url>
cd inmo

cp .env.example .env
# Editar .env con tus configuraciones

docker-compose up -d
```

Esto levanta: PostgreSQL, Redis, Backend (FastAPI), Celery Worker y Celery Beat.

## Instalación Manual

### 1. Base de Datos y Redis

```bash
# PostgreSQL
createdb lead_agent

# Redis (verificar que esté corriendo)
redis-cli ping
# Debe responder: PONG
```

### 2. Backend

```bash
cd backend

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.production.example .env
# Editar .env con tus valores
```

### 3. Configurar Variables de Entorno

Variables mínimas necesarias:

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@localhost:5432/lead_agent` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT secret (min 32 chars) | `tu-secret-key-super-segura-de-32-chars` |
| `GEMINI_API_KEY` | Google Gemini API key | `AIza...` |
| `ENVIRONMENT` | development / production | `development` |

Variables opcionales:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | Proveedor LLM | `gemini` |
| `VOICE_PROVIDER` | Proveedor de voz | `vapi` |
| `VAPI_API_KEY` | API key de VAPI | - |
| `TELEGRAM_TOKEN` | Token del bot de Telegram | - |
| `GOOGLE_CLIENT_ID` | Google Calendar OAuth | - |
| `GOOGLE_CLIENT_SECRET` | Google Calendar OAuth | - |
| `GOOGLE_REFRESH_TOKEN` | Google Calendar OAuth | - |
| `ALLOWED_ORIGINS` | CORS origins | `http://localhost:5173,http://localhost:3000` |
| `DEBUG` | Modo debug | `false` |

### 4. Migraciones de Base de Datos

```bash
cd backend

# Ejecutar migraciones
alembic upgrade head
```

### 5. Iniciar Backend

```bash
cd backend

# Servidor de desarrollo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Iniciar Celery Worker

```bash
cd backend

# Worker
celery -A app.tasks worker --loglevel=info

# Beat (scheduler) - en otra terminal
celery -A app.tasks beat --loglevel=info
```

### 7. Frontend

```bash
cd frontend

# Instalar dependencias
npm install

# Servidor de desarrollo
npm run dev
```

El frontend estará disponible en `http://localhost:5173`.

## Verificar Instalación

### Health Check

```bash
curl http://localhost:8000/health
```

Respuesta esperada:

```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

### Crear Primer Usuario

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@miinmobiliaria.com",
    "password": "MiPassword123",
    "broker_name": "Mi Inmobiliaria"
  }'
```

### Crear Superadmin

Para crear un superadmin, usar el script:

```bash
cd backend
python3 scripts/create_superadmin_simple.py
```

## Acceder al Sistema

| URL | Descripción |
|-----|-------------|
| `http://localhost:5173` | Frontend (React) |
| `http://localhost:8000` | Backend (API) |
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/redoc` | ReDoc |
