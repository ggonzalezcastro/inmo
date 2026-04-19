# Frontend Implementation Summary

**Versión**: 2.0 (Reescritura completa)
**Fecha**: 2026-02-27
**Stack**: React 18 · TypeScript (strict) · Vite · Shadcn/ui · Tailwind CSS · Zustand · React Router v6

---

## Arquitectura

El frontend sigue una arquitectura **feature-based (vertical slices)**. Cada módulo de negocio es autocontenido con sus propios componentes, servicios, store y tipos.

```
frontend/src/
├── app/
│   ├── App.tsx              # RouterProvider + Toaster (sonner)
│   └── router.tsx           # createBrowserRouter, lazy loading, guards
├── features/
│   ├── auth/
│   │   ├── components/      # LoginPage, RegisterPage
│   │   ├── hooks/           # useLogin, useRegister
│   │   ├── services/        # auth.service.ts
│   │   ├── store/           # authStore.ts (Zustand + localStorage compat)
│   │   └── index.ts
│   ├── dashboard/           # KPICard, PipelineSummary, HotLeadsList, DashboardPage
│   ├── leads/               # LeadsPage, LeadsTable, LeadDetail, LeadFormDialog, ImportCSVDialog
│   ├── pipeline/            # PipelinePage, KanbanColumn, KanbanCard
│   ├── campaigns/           # CampaignsPage
│   ├── appointments/        # AppointmentsPage
│   ├── templates/           # TemplatesPage, TemplateEditorDialog
│   ├── settings/            # SettingsPage (3 tabs: IA, Scoring, Preview)
│   ├── users/               # UsersPage
│   ├── brokers/             # BrokersPage
│   ├── chat/                # ChatPage (wrapper de ChatTest.jsx sin modificar)
│   └── llm-costs/           # CostsDashboardPage (feature pre-existente)
├── shared/
│   ├── components/
│   │   ├── ui/              # Shadcn/ui: Button, Dialog, Select, Tabs, Badge, etc.
│   │   ├── common/          # StatusBadge, ScoreBadge, DataTable, PageHeader, etc.
│   │   └── layout/          # AppShell, Sidebar (colapsable)
│   ├── guards/              # AuthGuard, RoleGuard
│   ├── hooks/               # usePermissions, useDebounce, usePagination
│   ├── lib/
│   │   ├── utils.ts         # cn(), formatCurrency, formatDate, getInitials, etc.
│   │   ├── constants.ts     # PIPELINE_STAGES, LEAD_STATUS_CONFIG, etc.
│   │   └── api-client.ts    # Axios con JWT interceptor (setTokenGetter pattern)
│   └── types/               # api.ts, auth.ts, common.ts
├── store/
│   └── authStore.js         # Shim de retrocompatibilidad → features/auth/store/authStore
├── styles/
│   └── globals.css          # Tokens CSS HSL (shadcn/ui), fuente Inter
└── main.tsx                 # ReactDOM.createRoot, StrictMode
```

---

## Decisiones Técnicas Clave

### Autenticación y Compatibilidad con Chat
El módulo `ChatTest.jsx` (chat con IA) no fue modificado: importa directamente de `src/store/authStore` y `src/services/api.js`. Para mantener compatibilidad:

1. `src/store/authStore.js` es un **shim** que re-exporta desde `features/auth/store/authStore.ts`
2. El nuevo store de TypeScript escribe el token en **Zustand Y `localStorage`** simultáneamente
3. Así el `api.js` original sigue leyendo el token sin cambios

### Routing y Lazy Loading
- `createBrowserRouter` de React Router v6
- Páginas de features cargadas con `React.lazy` + `Suspense` → mejor TTI
- `AuthGuard` envuelve el layout protegido; `RoleGuard` protege rutas específicas por rol
- Roles: `superadmin` (todo), `admin` (todo excepto brokers), `agent` (leads/pipeline/chat/citas)

### API Client
`shared/lib/api-client.ts` usa un patrón **`setTokenGetter(fn)`** en lugar de leer el token directamente. El auth store llama `setTokenGetter(() => token)` en `setAuth()`. Esto evita dependencias circulares.

### Componentes UI
Todos los componentes de `shared/components/ui/` están implementados manualmente sobre **Radix UI primitives** siguiendo la convención de Shadcn/ui. No se usa el CLI de shadcn/ui; los archivos están en el repositorio directamente.

---

## Features por Módulo

### Dashboard
- 4 KPI cards: leads totales, hot leads, agendados, tasa de conversión
- Resumen del pipeline con barras de progreso por etapa
- Lista de leads calientes con score badge

### Leads
- Tabla con paginación server-side usando `@tanstack/react-table`
- Filtros: búsqueda por nombre/teléfono, estado, calificación
- Panel lateral de detalle (datos financieros visibles solo para admin)
- Formulario de creación/edición en Dialog
- Importación masiva vía CSV

### Pipeline
- Kanban de **8 columnas** (entrada → ganado/perdido)
- Carga de todas las columnas en paralelo con `Promise.all`
- Mover lead a otra etapa desde un `DropdownMenu` hover (actualización optimista)
- Badge de inactividad (leads sin contacto en más de 7 días)

### Configuración (Settings)
- Tab **Agente IA**: nombre, identidad, system prompt
- Tab **Scoring**: umbrales por categoría (frío, cálido, caliente)
- Tab **Preview**: system prompt compilado completo

### Chat IA
`ChatPage` renderiza `ChatTest.jsx` como está, dentro del contenedor del AppShell. Ningún archivo del módulo de chat fue modificado.

---

## Permisos por Rol

| Módulo | agent | admin | superadmin |
|--------|-------|-------|------------|
| Dashboard | ✅ | ✅ | ✅ |
| Leads | ✅ | ✅ | ✅ |
| Pipeline | ✅ | ✅ | ✅ |
| Citas | ✅ | ✅ | ✅ |
| Chat IA | ✅ | ✅ | ✅ |
| Campañas | — | ✅ | ✅ |
| Templates | — | ✅ | ✅ |
| Costos LLM | — | ✅ | ✅ |
| Configuración | — | ✅ | ✅ |
| Usuarios | — | ✅ | ✅ |
| Brokers | — | — | ✅ |

---

## Dependencias Añadidas

```json
{
  "class-variance-authority": "^0.7.x",
  "clsx": "^2.x",
  "tailwind-merge": "^2.x",
  "lucide-react": "^0.x",
  "sonner": "^1.x",
  "@radix-ui/react-dialog": "^1.x",
  "@radix-ui/react-dropdown-menu": "^2.x",
  "@radix-ui/react-select": "^2.x",
  "@radix-ui/react-tabs": "^1.x",
  "@radix-ui/react-tooltip": "^1.x",
  "@radix-ui/react-avatar": "^1.x",
  "@radix-ui/react-progress": "^1.x",
  "@radix-ui/react-switch": "^2.x",
  "@radix-ui/react-popover": "^1.x",
  "@radix-ui/react-separator": "^1.x",
  "@radix-ui/react-label": "^2.x",
  "@tanstack/react-table": "^8.x"
}
```

---

## Comandos de Desarrollo

```bash
cd frontend

npm install
npm run dev          # http://localhost:5173
npm run build        # dist/

# TypeScript check (0 errores esperados)
npx tsc --noEmit --skipLibCheck
```

---

## Notas de Compatibilidad

- `src/store/authStore.js` **no borrar** — es el shim que mantiene vivo al módulo Chat
- `src/services/api.js` **no borrar** — lo usa ChatTest.jsx directamente
- `src/components/ChatTest.jsx` **no modificar** — constraint del proyecto
- `src/features/llm-costs/` — feature pre-existente en JavaScript; excluida parcialmente de tsc pero incluida en el bundle vía `router.tsx`
