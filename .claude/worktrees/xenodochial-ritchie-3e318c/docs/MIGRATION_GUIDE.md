# Guía de Migración - Reorganización del Proyecto

Esta guía describe los cambios realizados en la estructura del proyecto y cómo adaptar tu flujo de trabajo.

## Resumen de Cambios

### 1. Seguridad (Fase 0)

- **`.env.bak`** eliminado del seguimiento de git. Si tenías API keys en backups, **rótalas** (ver [docs/security/SECRETS_MANAGEMENT.md](security/SECRETS_MANAGEMENT.md)).
- **`.gitignore`** ampliado: `*.env.bak`, `token.pickle`, `credentials.json`, `celerybeat-schedule`, certificados, etc.
- **Pre-commit hooks**: configurados en `.pre-commit-config.yaml`. Instalar con `pre-commit install`.
- **Script de verificación**: `./scripts/check_security.sh` para comprobar que no se suban secrets.

### 2. Documentación

- Los archivos `.md` de la raíz se movieron a **`docs/`**:
  - `docs/api/` – arquitectura de API (ej. CHAT_PROVIDER_ARCHITECTURE.md)
  - `docs/deployment/` – despliegue (Vercel, Railway, checklist)
  - `docs/guides/` – guías (superadmin, roles, VAPI, Google Calendar)
  - `docs/architecture/` – auditoría, mejoras, integración pipeline
  - `docs/status/` – estado de implementación
  - `docs/technical/backend/` y `docs/technical/frontend/` – notas técnicas
- **README.md** permanece en la raíz.

### 3. Configuración

- **Docker**: `docker-compose.yml` está en **`config/docker/`**. Uso:
  ```bash
  docker-compose -f config/docker/docker-compose.yml up -d
  ```
- **Despliegue**: `vercel.json`, `railway.json`, `render.yaml`, `Procfile` están en **`config/deployment/`**.
- **Vercel**: se mantiene un **`vercel.json` en la raíz** para que Vercel lo detecte.

### 4. Backend

- **Config y base de datos**: la lógica está en **`app/core/config.py`** y **`app/core/database.py`**.
- **Compatibilidad**: `app/config.py` y `app/database.py` reexportan desde `core`, por lo que los imports existentes (`from app.config import settings`, `from app.database import get_db`) siguen funcionando.
- **Shared**: `app/shared/exceptions.py`, `app/shared/constants.py`, `app/shared/utils/` para excepciones, constantes y utilidades comunes.
- **Features**: se creó la estructura **`app/features/`** (auth, leads, campaigns, pipeline, appointments, chat, voice, broker, templates) para futura migración por dominios.

### 5. Frontend

- **Componentes compartidos**: en **`src/shared/components/ui/`**:
  - Modal, FormModal, StatusBadge, LoadingSpinner, ErrorMessage, Pagination, Alert
- **Hooks compartidos**: en **`src/shared/hooks/`**:
  - useFormValidation, useModal, useFilters, usePagination
- **Utilidades**: en **`src/shared/utils/`**:
  - validation.js, errorHandler.js, formatters.js, constants.js
- **Stores nuevos**: **`usersStore.js`** y **`brokersStore.js`** en `src/store/` para usuarios y brokers (usan `brokerAPI`).

## Cómo Usar lo Nuevo

- **UI**: importar desde `@/shared/components/ui` o rutas relativas, por ejemplo:
  ```js
  import { Modal, StatusBadge, LoadingSpinner } from '../shared/components/ui';
  ```
- **Hooks**: `import { useModal, useFormValidation } from '../shared/hooks';`
- **Errores API**: `import { handleApiError } from '../shared/utils/errorHandler';`
- **Usuarios/Brokers**: usar `useUsersStore()` y `useBrokersStore()` en lugar de llamar `brokerAPI` directamente en componentes.

## Referencias

- Gestión de secrets: [docs/security/SECRETS_MANAGEMENT.md](security/SECRETS_MANAGEMENT.md)
- Estructura actual: [README.md](../README.md) en la raíz del repo
