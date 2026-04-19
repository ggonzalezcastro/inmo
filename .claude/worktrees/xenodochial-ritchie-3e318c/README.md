# AI Lead Agent Pro

Sistema de gestión de leads inmobiliarios con inteligencia artificial integrada.

## Características

- ✅ Gestión completa de leads (CRUD)
- ✅ Autenticación JWT
- ✅ Integración con Telegram Bot
- ✅ Sistema de scoring de leads
- ✅ Base de datos PostgreSQL con SQLAlchemy async
- ✅ Cola de tareas con Celery y Redis
- ✅ API REST con FastAPI
- ✅ Docker Compose para desarrollo

## Estructura del Proyecto

```
inmo/
├── backend/
│   ├── app/
│   │   ├── core/            # Config, database, cache (app.core.config, app.core.database)
│   │   ├── shared/          # Exceptions, constants, utils
│   │   ├── features/        # Feature modules (auth, leads, campaigns, etc.)
│   │   ├── models/          # Modelos de base de datos
│   │   ├── schemas/         # Schemas Pydantic
│   │   ├── routes/          # Endpoints de la API
│   │   ├── services/        # Lógica de negocio
│   │   ├── tasks/           # Tareas de Celery
│   │   ├── middleware/      # Middleware (auth, etc)
│   │   ├── config.py        # Re-export from core (compat)
│   │   ├── database.py      # Re-export from core (compat)
│   │   ├── main.py          # Aplicación FastAPI
│   │   └── celery_app.py    # Configuración Celery
│   ├── migrations/          # Migraciones Alembic
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── shared/          # Componentes UI, hooks, utils
│       ├── components/      # Componentes por página
│       ├── pages/
│       ├── store/
│       └── services/
├── docs/                    # Documentación (api, deployment, guides, architecture)
├── config/                  # Configuración (docker, deployment)
│   ├── docker/              # docker-compose.yml
│   └── deployment/          # vercel, railway, render, Procfile
├── scripts/                 # Scripts globales (check_security.sh)
├── vercel.json              # Vercel (raíz para que Vercel lo detecte)
└── README.md
```

## Requisitos Previos

- Docker y Docker Compose
- Python 3.11+ (para desarrollo local)
- PostgreSQL 15+ (si no usas Docker)
- Redis (si no usas Docker)

## Configuración

1. **Clonar el repositorio** (si aplica)

2. **Configurar variables de entorno**

   Copia `.env.example` a `.env` y configura las variables:

   ```bash
   cp .env.example .env
   ```

   Edita `.env` con tus valores (nunca hagas commit de `.env`; ver [docs/security/SECRETS_MANAGEMENT.md](docs/security/SECRETS_MANAGEMENT.md)):
   - `SECRET_KEY`: Clave secreta para JWT (mínimo 32 caracteres; generar con `openssl rand -hex 32`)
   - `GEMINI_API_KEY` / `OPENAI_API_KEY`: API keys de LLM
   - `TELEGRAM_TOKEN`: Token de tu bot de Telegram

3. **Iniciar servicios con Docker Compose**

   ```bash
   docker-compose -f config/docker/docker-compose.yml up -d
   ```

   (O desde la raíz del repo; el compose está en `config/docker/`.)

   Esto iniciará:
   - PostgreSQL en puerto 5432
   - Redis en puerto 6379
   - Backend FastAPI en puerto 8000
   - Celery worker
   - Celery beat (scheduler)

4. **Ejecutar migraciones**

   ```bash
   docker-compose -f config/docker/docker-compose.yml exec backend alembic upgrade head
   ```

## Desarrollo Local

Si prefieres desarrollar sin Docker:

1. **Crear entorno virtual**

   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

2. **Instalar dependencias**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configurar base de datos**

   Asegúrate de que PostgreSQL y Redis estén corriendo, y configura `DATABASE_URL` y `REDIS_URL` en `.env`.

4. **Ejecutar migraciones**

   ```bash
   alembic upgrade head
   ```

5. **Iniciar servidor**

   ```bash
   uvicorn app.main:app --reload
   ```

## API Endpoints

### Autenticación

- `POST /auth/register` - Registrar nuevo usuario
- `POST /auth/login` - Iniciar sesión

### Leads

- `GET /api/v1/leads` - Listar leads (con filtros)
- `GET /api/v1/leads/{id}` - Obtener lead específico
- `POST /api/v1/leads` - Crear nuevo lead
- `PUT /api/v1/leads/{id}` - Actualizar lead
- `DELETE /api/v1/leads/{id}` - Eliminar lead
- `POST /api/v1/leads/bulk-import` - Importar leads desde CSV

### Health Check

- `GET /health` - Estado del sistema

## Documentación API

Una vez que el servidor esté corriendo, accede a:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Características Implementadas

- ✅ Integración con Telegram Bot
- ✅ Sistema de scoring de leads automático
- ✅ Frontend React con Vite
- ✅ Dashboard de analytics
- ✅ Procesamiento de mensajes con IA (OpenAI)
- ✅ Recalculo diario de scores (Celery Beat)
- ✅ Importación masiva de leads (CSV)

## Uso del Sistema

### 1. Configurar Telegram Bot

1. Crea un bot en Telegram con [@BotFather](https://t.me/botfather)
2. Obtén el token del bot
3. Configura el webhook:

```bash
curl -X POST http://localhost:8000/api/v1/telegram/webhook/setup \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"webhook_url": "https://yourdomain.com/webhooks/telegram"}'
```

### 2. Probar el Bot

Envía un mensaje a tu bot en Telegram. El sistema:
- Creará automáticamente un lead
- Generará una respuesta con IA
- Calculará el score del lead
- Actualizará el status (cold/warm/hot)

### 3. Ver Leads en el Dashboard

Accede a http://localhost:5173 y:
- Filtra por status, score, o búsqueda
- Ve estadísticas en tiempo real
- Importa leads desde CSV

## Estructura de Tareas Celery

- `process_telegram_message`: Procesa mensajes entrantes de Telegram
- `recalculate_all_lead_scores`: Recalcula scores diariamente (2 AM UTC)

## API Endpoints Adicionales

### Telegram

- `POST /api/v1/telegram/webhook/setup` - Configurar webhook
- `GET /api/v1/telegram/webhook/info` - Información del webhook

### Webhooks

- `POST /webhooks/telegram` - Endpoint para recibir actualizaciones de Telegram

## Desarrollo

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Iniciar servidor
uvicorn app.main:app --reload

# Iniciar Celery worker
celery -A app.celery_app worker --loglevel=info

# Iniciar Celery beat
celery -A app.celery_app beat --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Docker Compose

```bash
docker-compose up -d
```

## Variables de Entorno Requeridas

Ver `ENV_VARIABLES.md` para la lista completa. Las más importantes:

- `OPENAI_API_KEY`: Tu API key de OpenAI
- `TELEGRAM_TOKEN`: Token del bot de Telegram
- `SECRET_KEY`: Clave secreta para JWT (mínimo 32 caracteres)
- `DATABASE_URL`: URL de conexión a PostgreSQL
- `REDIS_URL`: URL de conexión a Redis

## 🚀 Deployment a Producción

Este proyecto está **100% preparado** para deployment en Vercel (frontend) y Railway/Render/Heroku (backend).

### Guías de Deployment Disponibles

1. **[README_VERCEL_QUICKSTART.md](./README_VERCEL_QUICKSTART.md)** - 🚀 Guía rápida (5 minutos)
2. **[DEPLOYMENT_VERCEL.md](./DEPLOYMENT_VERCEL.md)** - 📚 Guía completa y detallada
3. **[DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)** - ✅ Checklist paso a paso

### Arquitectura de Deployment

```
┌─────────────────────┐
│   Vercel (CDN)      │  ← Frontend (React + Vite)
│   tu-app.vercel.app │
└──────────┬──────────┘
           │ HTTPS
           ↓
┌─────────────────────┐
│  Railway/Render     │  ← Backend (FastAPI)
│  PostgreSQL + Redis │
│  Celery Workers     │
└─────────────────────┘
```

### Quick Start

```bash
# 1. Subir a Git
git init
git add .
git commit -m "Ready for deployment"
git push origin main

# 2. Deploy Backend en Railway
# → https://railway.app
# → Conectar repo → Add PostgreSQL → Add Redis

# 3. Deploy Frontend en Vercel
# → https://vercel.com
# → Import project → Configura VITE_API_URL

# ¡Listo! 🎉
```

### URLs de Producción

Después del deployment, tu app estará en:
- **Frontend**: `https://tu-app.vercel.app`
- **Backend API**: `https://tu-backend.railway.app`
- **API Docs**: `https://tu-backend.railway.app/docs`

---

## Licencia

MIT

