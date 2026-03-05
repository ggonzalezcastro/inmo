# Plan: Saneamiento Completo Frontend React

El proyecto tiene una arquitectura nueva bien diseñada (`src/app/`, `src/features/`, `src/shared/`) que ya está activa (`index.html` apunta a `main.tsx`), pero coexiste con código legado nunca eliminado, zero tooling de calidad, y zero tests. Este plan lo expurga ordenadamente en 6 fases secuenciales, de mayor riesgo a menor, y sienta la base para escalar con confianza.

---

### Fase 1 — Correcciones Críticas (urgente, sin tocar lógica de negocio)

**1.1 — Corregir mismatch `@types/react` v19 vs React v18**

- Editar `package.json`: bajar `@types/react` de `^19.2.14` a `^18.3.x` y `@types/react-dom` de `^19.2.3` a `^18.3.x`
- Ejecutar `npm install` y verificar que `tsc --noEmit` pase sin errores nuevos

**1.2 — Eliminar `vite.config.js` duplicado**

- Eliminar `vite.config.js` — Vite usa `.ts` con mayor prioridad pero el `.js` puede tener opciones inconsistentes que se aplican en algunos ambientes
- Solo conservar `vite.config.ts`

**1.3 — Eliminar código legado confirmado como muerto**

- `index.html` apunta a `main.tsx` → los siguientes archivos son código muerto puro:
  - Eliminar `src/main.jsx`
  - Eliminar `src/App.jsx`
  - Eliminar toda la carpeta `src/store/` (los 8 archivos `.js` de Zustand legado)
  - Nota: **NO** eliminar `src/components/ChatTest.jsx` todavía — sigue siendo requerido por `src/features/chat/pages/ChatPage.tsx`

**1.4 — Desinstalar `react-beautiful-dnd`**

- Librería abandonada (último commit 2022), incompatible con React 18 StrictMode
- Verificar con grep qué archivos la importan: si solo es código legado ya eliminado, `npm uninstall react-beautiful-dnd` directamente
- Si algún componente nuevo la usa, migrar ese componente a `@dnd-kit` (ya instalado)

**1.5 — Agregar scripts esenciales a `package.json`**

- Agregar a la sección `scripts`:
  - `"type-check": "tsc --noEmit"`
  - `"lint": "eslint src --ext .ts,.tsx,.js,.jsx --report-unused-disable-directives"`
  - `"test": "vitest"`

---

### Fase 2 — Tooling de Calidad (ESLint + Prettier + Vitest)

**2.1 — Instalar y configurar ESLint**

- Instalar: `eslint @typescript-eslint/eslint-plugin @typescript-eslint/parser eslint-plugin-react eslint-plugin-react-hooks eslint-plugin-jsx-a11y`
- Crear `.eslintrc.cjs` en `frontend/` con config que extienda: `plugin:@typescript-eslint/recommended`, `plugin:react-hooks/recommended`, `plugin:jsx-a11y/recommended`
- La regla `react-hooks/exhaustive-deps` capturará el bug en `src/hooks/useRealtime.js` (dependencia `onUpdate` faltante) automáticamente

**2.2 — Instalar y configurar Prettier**

- Instalar: `prettier eslint-config-prettier`
- Crear `.prettierrc` con `singleQuote: true`, `semi: false`, `printWidth: 100`, `tabWidth: 2`
- Agregar `eslint-config-prettier` al final de `extends` en `.eslintrc.cjs` para evitar conflictos

**2.3 — Instalar Vitest + React Testing Library**

- Instalar: `vitest @vitest/ui jsdom @testing-library/react @testing-library/user-event @testing-library/jest-dom`
- Crear `vitest.config.ts` en `frontend/` con `environment: 'jsdom'` y `setupFiles: ['./src/test/setup.ts']`
- Crear `src/test/setup.ts` con el import `@testing-library/jest-dom/vitest`

**2.4 — Tests iniciales para lógica crítica**

- Crear `src/features/auth/store/authStore.test.ts`: testear `setAuth`, `clearAuth`, `isLoggedIn()`, `decodeJWT` con token válido e inválido
- Crear `src/shared/hooks/usePermissions.test.ts`: testear que cada rol devuelve el conjunto correcto de permisos
- Crear `src/shared/guards/AuthGuard.test.tsx`: testear redirect a `/login` cuando no autenticado, render de `children` cuando sí lo está

---

### Fase 3 — Corrección del Bug de `useRealtime` + Migración a WebSocket

**3.1 — Corregir el stale callback en `useRealtime.js`**

- En `src/hooks/useRealtime.js`: usar el patrón `useRef` para el callback
  - Añadir `const onUpdateRef = useRef(onUpdate)` y `useEffect(() => { onUpdateRef.current = onUpdate })`
  - Dentro del poll, llamar `onUpdateRef.current?.(response.data)` en lugar de `onUpdate?.(response.data)`
  - Eliminar `onUpdate` del array de dependencias del `useEffect` principal

**3.2 — Crear `useWebSocket` hook en `src/shared/hooks/`**

- Crear `src/shared/hooks/useWebSocket.ts`: hook que gestiona la conexión al endpoint `/ws/{broker_id}` del backend
  - Reconexión automática con backoff exponencial (empezar en 1s, máximo 30s)
  - Cleanup del WebSocket en el unmount del componente
  - Emitir eventos tipados: `new_message | stage_changed | lead_assigned | lead_hot | typing`
- Mover `src/hooks/useRealtime.js` a `src/shared/hooks/useRealtime.ts` (TypeScript) y actualizar imports

**3.3 — Conectar el nuevo hook a los componentes que hoy usan polling**

- Identificar los componentes que llaman `useRealtime` o `usePipelineRealtime`
- Reemplazar el polling por `useWebSocket` para actualizaciones del pipeline y del chat
- El `useRealtime` puede mantenerse como fallback para endpoints sin eventos WS

---

### Fase 4 — Limpieza de Duplicados en `src/shared/`

**4.1 — Eliminar hooks JS duplicados**

- `shared/hooks/usePagination.js` → eliminar (existe `usePagination.ts`)
- `useModal.js`, `useFilters.js`, `useFormValidation.js` — verificar si algún componente activo los usa; si no, eliminar; si sí, migrar a TypeScript

**4.2 — Eliminar componentes UI `.jsx` duplicados en `shared/components/ui/`**

Archivos a evaluar: `Alert.jsx`, `ErrorMessage.jsx`, `FormModal.jsx`, `LoadingSpinner.jsx`, `Modal.jsx`, `Pagination.jsx`, `StatusBadge.jsx`
- Para cada `.jsx`, verificar con grep qué archivos lo importan
- Si solo lo usan componentes legados ya eliminados → borrar directamente
- Si aún hay imports activos → migrar a `.tsx` tipado y actualizar los imports

**4.3 — Consolidar `shared/hooks/index.js` a TypeScript**

- Renombrar a `index.ts` y actualizar los re-exports para apuntar a las versiones `.ts` de los hooks

---

### Fase 5 — Migración de `ChatTest.jsx` (la deuda técnica mayor)

**5.1 — Auditar `ChatTest.jsx`**

- Leer el archivo completo
- Mapear: qué APIs consume, qué estado maneja, qué subcomponentes tiene, qué props acepta

**5.2 — Crear nueva feature `chat` completa**

- Crear `src/features/chat/components/ChatPage.tsx` como componente real (no wrapper)
- Extraer lógica de mensajes a `src/features/chat/hooks/useChat.ts`
- Extraer conexión WebSocket a `src/features/chat/hooks/useChatWebSocket.ts` (usando el `useWebSocket` de fase 3)
- Tipar todos los mensajes con los tipos del backend (`new_message`, `typing`)
- Añadir `aria-live="polite"` en el contenedor de mensajes, `aria-label` en el input

**5.3 — Eliminar `ChatTest.jsx` y actualizar `ChatPage.tsx`**

- Una vez que el nuevo componente pase revisión manual, eliminar `src/components/ChatTest.jsx`
- Actualizar `src/features/chat/index.ts` para exportar el nuevo `ChatPage`

---

### Fase 6 — Accesibilidad (a11y) mínima viable

**6.1 — `aria-label` en todos los botones de icono**

- Buscar con grep `size="icon"` en todos los `.tsx` de `src/`
- Añadir `aria-label` descriptivo a cada uno. Ejemplo: `<Button size="icon" aria-label="Cerrar detalle">`

**6.2 — Keyboard navigation en Kanban**

- En `KanbanColumn.tsx`: configurar `KeyboardSensor` en `DndContext` de `@dnd-kit`
- Añadir `announcements` al `DndContext`: `"Lead X movido a columna Y"`

**6.3 — `aria-live` en áreas de actualización dinámica**

- Añadir `role="status"` o `aria-live="polite"` al board del pipeline

---

### Verificación

```bash
cd frontend

# Tipos
npm run type-check           # 0 errores

# Linting
npm run lint                 # 0 errores, 0 warnings

# Tests
npm run test                 # authStore ✓, usePermissions ✓, AuthGuard ✓

# Build de producción
npm run build                # Sin warnings de bundle size inesperados

# Manual: navegar con Tab por el pipeline Kanban
# Manual: verificar que el chat funciona sin el calc() hack de layout