# Guía de Inicio Rápido

> Última actualización: 2026-04-18

## Prerequisites

### Software requerido

| Software | Versión mínima | Notas |
|----------|---------------|-------|
| Node.js | 18+ | Para frontend |
| Python | 3.11+ | Para backend |
| Docker | 24+ | Para servicios local |
| Docker Compose | 2.20+ | Orquestación |
| Git | 2.40+ | Control de versiones |

### Cuentas API necesarias

| Servicio | Required | Notas |
|----------|----------|-------|
| Gemini API Key | Sí (producción) | googleai.google.dev |
| Telegram Bot Token | No | Solo si usas Telegram |
| WhatsApp Business | No | Solo si usas WhatsApp |
| VAPI | No | Solo si usas voz |

---

## Setup Local (Desarrollo)

### 1. Clonar el repositorio

```bash
git clone <repo-url>
cd inmo
```

### 2. Configurar variables de entorno

```bash
# Backend
cp backend/.env.example backend/.env
# Editar backend/.env con tus API keys

#Frontend
cp frontend/.env.example frontend/.env.local
```

### 3. Variables de entorno mínimas para desarrollo

```bash
# backend/.env
DATABASE_URL=postgresql+asyncpg://lead_user:lead_pass_123@localhost:5432/lead_agent
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=dev-secret-key-change-in-production
GEMINI_API_KEY=your_gemini_api_key
LLM_PROVIDER=gemini
```

### 4. Iniciar servicios con Docker

```bash
docker-compose up -d db redis
```

### 5. Ejecutar migraciones

```bash
cd backend
source .venv/bin/activate  # o pip install -r requirements.txt
alembic upgrade head
```

### 6. Iniciar backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### 7. Iniciar frontend

```bash
cd frontend
npm install
npm run dev
```

### 8. Verificar que funciona

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Docker Compose (Desarrollo Completo)

Para desarrollo local con todos los servicios:

```bash
docker-compose up -d
```

Servicios iniciados:

| Servicio | Puerto | Descripción |
|----------|---------|-------------|
| frontend | 5173 | React dev server |
| backend | 8000 | FastAPI |
| db | 5432 | PostgreSQL + pgvector |
| redis | 6379 | Cache + Celery broker |
| mcp-server | 8001 | MCP tool server |

---

## Primeros Pasos para Nuevos Desarrolladores

### 1. Entender la arquitectura

Lee estos documentos en orden:

1. [[arquitectura/overview]] - Visión general del sistema
2. [[arquitectura/multi-agente]] - Cómo trabajan los agentes IA
3. [[frontend/structure]] - Estructura del frontend

### 2. Revisar el flujo de un lead

```
WhatsApp/Telegram/Webchat
    ↓
ChatOrchestratorService.process_chat_message()
    ↓
Sentiment Analysis (sync heuristics)
    ↓
AgentSupervisor.process()
    ↓
QualifierAgent → SchedulerAgent → FollowUpAgent
    ↓
LLMServiceFacade (Gemini/Claude/OpenAI)
    ↓
Response + WebSocket broadcast
```

### 3. Archivos clave a conocer

| Archivo | Propósito |
|---------|----------|
| `backend/app/services/chat/orchestrator.py` | Punto de entrada del chat |
| `backend/app/services/agents/supervisor.py` | Router de agentes |
| `backend/app/services/llm/facade.py` | Capa LLM |
| `frontend/src/app/router.tsx` | Rutas del frontend |
| `frontend/src/store/authStore.ts` | Estado de autenticación |

### 4. Hacer un cambio pequeño

1. Crea un broker de prueba via `/auth/register`
2. Envia un mensaje de prueba via `/chat/test`
3. Observa los logs del backend
4. Revisa la respuesta en el frontend

---

## Comandos Útiles

### Backend

```bash
# Activar virtualenv
source backend/.venv/bin/activate

# Servidor de desarrollo
uvicorn app.main:app --reload --port 8000

# Worker de Celery
celery -A app.celery_app worker --loglevel=info

# Beat (tareas periódicas)
celery -A app.celery_app beat --loglevel=info

# Migraciones
alembic upgrade head
alembic revision --autogenerate -m "tu mensaje"

# Tests
pytest tests/ -v
```

### Frontend

```bash
cd frontend
npm install          # Instalar dependencias
npm run dev         # Dev server en :5173
npm run build       # Build producción
npm run lint        # Linting
```

### Docker

```bash
docker-compose up -d                # Iniciar todos
docker-compose logs -f backend      # Ver logs del backend
docker-compose exec backend bash     # Shell en el contenedor
docker-compose down                 # Detener todos
```

---

## Issues Comunes y Soluciones

### "Connection refused" en PostgreSQL

```bash
# Verificar que PostgreSQL está corriendo
docker-compose ps db

# Esperar a que esté healthy
docker-compose up -d db
docker-compose logs db --tail=20
```

### "Module not found" en Python

```bash
# Reinstalar dependencias
pip install -r requirements.txt

# Verificar que el venv está activado
which python  # debe指向 .venv/bin/python
```

### CORS errors en el navegador

```bash
# Verificar FRONTEND_URL en backend/.env
FRONTEND_URL=http://localhost:5173

# Reiniciar backend
```

### Redis connection refused

```bash
docker-compose up -d redis
docker-compose logs redis --tail=10
```

---

## Siguientes Pasos

- [[guides/development]] - Workflow de desarrollo detallado
- [[guides/USAGE_GUIDE]] - Cómo usar el sistema
- [[guides/ENV_VARIABLES]] - Variables de entorno completas
- [[bugs-conocidos]] - Bugs y tech debt conocidos

---

## Changelog

| Fecha | Descripción |
|--------|-------------|
| 2026-04-18 | Creación del getting started guide |
| 2026-04-17 | Agregada sección de primeros pasos para nuevos desarrolladores |
