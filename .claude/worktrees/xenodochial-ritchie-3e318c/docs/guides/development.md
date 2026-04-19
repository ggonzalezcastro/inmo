---
title: Guía de Desarrollo
version: 1.0.0
date: 2026-02-21
author: Equipo Inmo
---

# Guía de Desarrollo

## Estructura del Proyecto

```
inmo/
├── backend/
│   ├── app/
│   │   ├── core/                  # Configuración, database, cache
│   │   │   ├── config.py          # Settings (Pydantic)
│   │   │   ├── database.py        # Async SQLAlchemy setup
│   │   │   └── cache.py           # Redis cache
│   │   ├── middleware/            # Auth, rate limiting, permisos
│   │   │   ├── auth.py            # JWT authentication
│   │   │   ├── permissions.py     # Role-based access
│   │   │   └── rate_limiter.py    # Redis rate limiting
│   │   ├── models/                # SQLAlchemy models
│   │   │   ├── base.py            # IdMixin, TimestampMixin
│   │   │   ├── broker.py          # Broker, configs, campaigns
│   │   │   └── lead.py            # Lead, messages, activities
│   │   ├── routes/                # FastAPI routers
│   │   ├── schemas/               # Pydantic request/response
│   │   ├── services/              # Business logic
│   │   │   ├── voice/             # Voice providers
│   │   │   ├── llm/               # LLM providers
│   │   │   ├── chat/              # Chat providers
│   │   │   ├── broker/            # Broker config
│   │   │   ├── leads/             # Lead management
│   │   │   ├── pipeline/          # Sales pipeline
│   │   │   ├── appointments/      # Scheduling
│   │   │   ├── campaigns/         # Marketing campaigns
│   │   │   └── shared/            # Cross-domain services
│   │   ├── tasks/                 # Celery background tasks
│   │   └── main.py                # App entrypoint
│   ├── migrations/                # Alembic migrations
│   ├── scripts/                   # Utility scripts
│   ├── tests/                     # Test suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/                   # Router (router.tsx) y App root (App.tsx)
│   │   ├── features/              # Vertical slices por dominio
│   │   │   ├── auth/              # store/, services/, hooks/, components/, index.ts
│   │   │   ├── dashboard/
│   │   │   ├── leads/
│   │   │   ├── pipeline/
│   │   │   ├── campaigns/
│   │   │   ├── appointments/
│   │   │   ├── templates/
│   │   │   ├── settings/
│   │   │   ├── users/
│   │   │   ├── brokers/
│   │   │   ├── chat/              # Wrapper de ChatTest.jsx (sin modificar)
│   │   │   └── llm-costs/
│   │   ├── shared/
│   │   │   ├── components/
│   │   │   │   ├── ui/            # Shadcn/ui (Button, Dialog, Select, etc.)
│   │   │   │   ├── common/        # StatusBadge, ScoreBadge, DataTable, etc.
│   │   │   │   └── layout/        # AppShell, Sidebar
│   │   │   ├── guards/            # AuthGuard, RoleGuard
│   │   │   ├── hooks/             # usePermissions, useDebounce, usePagination
│   │   │   ├── lib/               # utils.ts, constants.ts, api-client.ts
│   │   │   └── types/             # api.ts, auth.ts, common.ts
│   │   ├── store/                 # authStore.js (shim de retrocompat → features/auth)
│   │   ├── styles/                # globals.css (tokens CSS shadcn/ui)
│   │   └── main.tsx               # Entry point
│   ├── vite.config.ts             # Alias @/ → src/
│   └── tsconfig.json
├── config/                        # Deployment configs
├── docker-compose.yml
└── docs/                          # This documentation
```

## Convenciones de Código

### Backend (Python)

| Convención | Ejemplo |
|-----------|---------|
| Archivos | `snake_case.py` |
| Clases | `PascalCase` |
| Funciones | `snake_case()` |
| Variables | `snake_case` |
| Constantes | `UPPER_SNAKE_CASE` |
| Modelos SQLAlchemy | Singular: `Lead`, `Broker` |
| Tablas | Plural: `leads`, `brokers` |
| Rutas | Plural: `/api/v1/leads` |

### Frontend (TypeScript/React)

| Convención | Ejemplo |
|-----------|---------|
| Componentes | `PascalCase.tsx` |
| Lógica pura (hooks, stores, services) | `camelCase.ts` |
| Stores Zustand | `camelCaseStore.ts` en `features/<name>/store/` |
| Servicios API | `<name>.service.ts` en `features/<name>/services/` |
| Exports | Barrel `index.ts` por feature |
| CSS | Tailwind utility classes + variables CSS HSL |
| Imports internos | Alias `@/` (ej. `@/shared/lib/utils`) |

## Agregar un Nuevo Proveedor de Voz

El sistema usa Strategy Pattern para proveedores. Para agregar un nuevo proveedor:

### 1. Crear el módulo del proveedor

```
backend/app/services/voice/providers/my_provider/
├── __init__.py
└── provider.py
```

### 2. Implementar la interfaz

```python
from app.services.voice.base_provider import BaseVoiceProvider
from app.services.voice.types import (
    MakeCallRequest, CallStatusResult, WebhookEvent,
    VoiceProviderType, CallEventType
)

class MyProvider(BaseVoiceProvider):

    async def make_call(self, request: MakeCallRequest) -> str:
        # Retorna external_call_id
        ...

    async def get_call_status(self, call_id: str) -> CallStatusResult:
        ...

    async def handle_webhook(self, payload: dict) -> WebhookEvent:
        # Normalizar payload del proveedor a WebhookEvent
        ...

    async def cancel_call(self, call_id: str) -> bool:
        ...

    def get_provider_type(self) -> VoiceProviderType:
        return VoiceProviderType.MY_PROVIDER
```

### 3. Registrar en la factory

En `backend/app/services/voice/factory.py`:

```python
from app.services.voice.providers.my_provider import MyProvider

register_voice_provider(VoiceProviderType.MY_PROVIDER, MyProvider)
```

### 4. Agregar configuración

En `backend/app/core/config.py`:

```python
MY_PROVIDER_API_KEY: str = ""
```

## Agregar un Nuevo Endpoint

### 1. Crear schema (si necesario)

En `backend/app/schemas/`:

```python
from pydantic import BaseModel

class MyRequest(BaseModel):
    field: str

class MyResponse(BaseModel):
    id: int
    field: str
```

### 2. Agregar ruta

En `backend/app/routes/my_route.py`:

```python
from fastapi import APIRouter, Depends
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/my-resource", tags=["my-resource"])

@router.get("/")
async def list_resources(current_user=Depends(get_current_user)):
    ...
```

### 3. Incluir router en main.py

```python
from app.routes import my_route
app.include_router(my_route.router)
```

## Migraciones de Base de Datos

```bash
cd backend

# Crear nueva migración
alembic revision --autogenerate -m "descripción del cambio"

# Aplicar migraciones
alembic upgrade head

# Revertir última migración
alembic downgrade -1

# Ver historial
alembic history
```

## Testing

```bash
cd backend

# Instalar dependencias de test
pip install -r requirements-test.txt

# Ejecutar tests
pytest

# Con cobertura
pytest --cov=app --cov-report=html

# Solo un archivo
pytest tests/services/test_voice_providers.py -v
```

## Debugging

### Logs

El backend usa `logging` de Python con diferentes niveles:

```python
import logging
logger = logging.getLogger(__name__)

logger.debug("Detalle de debugging")
logger.info("Operación completada")
logger.warning("Algo inesperado")
logger.error("Error", exc_info=True)
```

### Swagger UI

Disponible en `http://localhost:8000/docs` para probar endpoints interactivamente.

### Redis CLI

```bash
redis-cli
> KEYS *               # Ver todas las claves
> GET "lead:ctx:123"   # Ver contexto cacheado de un lead
> TTL "lead:ctx:123"   # Ver TTL de una clave
```
