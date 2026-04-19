# Guía de Desarrollo

> Última actualización: 2026-04-18

## Estructura del Proyecto

```
inmo/
├── backend/              # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── features/    # Vertical slices (auth, leads, chat, etc.)
│   │   ├── routes/     # Endpoint implementations
│   │   ├── services/   # Business logic
│   │   │   ├── agents/        # Multi-agent system
│   │   │   ├── chat/         # Chat orchestrator
│   │   │   ├── llm/          # LLM providers
│   │   │   ├── pipeline/    # Pipeline stages
│   │   │   └── sentiment/    # Sentiment analysis
│   │   ├── core/      # Config, encryption, websockets
│   │   ├── models/    # SQLAlchemy models
│   │   ├── tasks/     # Celery tasks
│   │   └── mcp/       # MCP server
│   ├── migrations/     # Alembic migrations
│   └── tests/          # Pytest tests
├── frontend/           # React + Vite + TypeScript
│   ├── src/
│   │   ├── features/  # Feature modules
│   │   ├── shared/    # Shared components
│   │   ├── store/     # Zustand stores
│   │   └── app/       # Router, App.tsx
│   └── tests/          # Frontend tests
└── docs/               # Esta documentación
```

---

## Backend Development

### Setup del entorno

```bash
cd backend

# Crear virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Variables de entorno
cp .env.example .env
# Editar .env con tus credenciales
```

### Base de datos

```bash
# Crear migración
alembic revision --autogenerate -m "Descripción del cambio"

# Ejecutar migraciones
alembic upgrade head

# Rollback
alembic downgrade -1

# Ver estado
alembic current
alembic history
```

### Servidor de desarrollo

```bash
# Activar venv y correr
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Con logs verbose
uvicorn app.main:app --reload --log-level debug
```

### Tareas Celery

```bash
# Worker principal
celery -A app.celery_app worker --loglevel=info

# Beat (tareas periódicas)
celery -A app.celery_app beat --loglevel=info

# Ambos en foreground (desarrollo)
celery -A app.celery_app worker --loglevel=info --beat --loglevel=info
```

### Tests

```bash
# Todos los tests (requiere Docker services)
pytest tests/ -v

# Tests unitarios (sin DB)
pytest tests/services/test_multi_agent.py -v --noconftest

# Tests de un módulo específico
pytest tests/services/ -v

# Coverage
pytest tests/ --cov=app --cov-report=html
```

### Patrones de código

**Modelos SQLAlchemy:**

```python
from app.models.base import Base, IdMixin, TimestampMixin

class MyModel(Base, IdMixin, TimestampMixin):
    __tablename__ = "my_table"

    name = Column(String(100), nullable=False)
    status = Column(String(20), default="active")
    metadata = Column(JSONB, default={})

    # Índices
    __table_args__ = (
        Index('idx_name_status', 'name', 'status'),
    )
```

**Rutas FastAPI:**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth import get_current_user

router = APIRouter()

@router.get("/items")
async def list_items(
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Filtrar por broker_id del usuario actual
    broker_id = current_user.get("broker_id")
    items = await ItemService.get_items(db, broker_id, skip, limit)
    return {"items": items}
```

**Servicios:**

```python
class MyService:
    @staticmethod
    async def get_items(db: AsyncSession, broker_id: int, skip: int, limit: int):
        result = await db.execute(
            select(Item)
            .where(Item.broker_id == broker_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
```

---

## Frontend Development

### Setup

```bash
cd frontend
npm install
npm run dev
```

### Estructura

```
src/
├── app/
│   ├── router.tsx      # Definición de rutas
│   └── App.tsx        # Componente raíz
├── features/
│   ├── auth/          # Login, registro
│   ├── leads/         # Gestión de leads
│   ├── pipeline/      # Vista kanban
│   └── ...
├── shared/
│   ├── components/    # Componentes compartidos
│   ├── context/       # React contexts
│   ├── guards/        # AuthGuard, RoleGuard
│   └── lib/           # API client, utils
└── store/
    ├── authStore.ts   # Estado de autenticación
    └── ...
```

### Patrones de código

**Zustand Store:**

```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AuthState {
  user: User | null
  token: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      login: async (email, password) => {
        const response = await authAPI.login(email, password)
        set({ token: response.token, user: response.user })
      },
      logout: () => set({ user: null, token: null }),
    }),
    { name: 'auth-storage' }
  )
)
```

**Componente con guards:**

```typescript
import { AuthGuard } from '@/shared/guards/AuthGuard'
import { RoleGuard } from '@/shared/guards/RoleGuard'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/admin"
        element={
          <AuthGuard>
            <RoleGuard allowedRoles={['admin', 'superadmin']}>
              <AdminPage />
            </RoleGuard>
          </AuthGuard>
        }
      />
    </Routes>
  )
}
```

---

## Debugging

### Backend

```python
# Logging
import logging
logger = logging.getLogger(__name__)

logger.info("Mensaje de info")
logger.error(f"Error: {e}", exc_info=True)
```

```bash
# Logs en tiempo real
tail -f backend/logs/app.log

# Verbose uvicorn
uvicorn app.main:app --log-level debug
```

### Frontend

```typescript
// Debug en componente
console.log("state:", state)

// React DevTools
// Instalar extensión del navegador
```

### Base de datos

```sql
-- Ver queries lentas
SELECT * FROM pg_stat_activity WHERE state = 'active';

-- Ver locks
SELECT * FROM pg_locks;

-- Stats de tablas
SELECT * FROM pg_stat_user_tables WHERE relname = 'leads';
```

---

## Code Quality

### Backend

```bash
# Formatear código
black app/
isort app/

# Linting
ruff check app/

# Type checking
mypy app/
```

### Frontend

```bash
# Formatear y lint
npm run lint
npm run lint:fix

# Type check
npm run typecheck
```

---

## Hot Reload

### Backend

Uvicorn tiene hot reload por defecto con `--reload`. Los cambios en Python se recargan automáticamente.

### Frontend

Vite tiene hot module replacement (HMR). Los cambios en React se recargan sin perder estado.

### Docker Compose

```bash
# Editar código directamente (mapeado al contenedor)
# Los cambios se recargan automáticamente
docker-compose up -d backend
```

---

## Changelog

| Fecha | Descripción |
|--------|-------------|
| 2026-04-18 | Creación del guide de desarrollo |
