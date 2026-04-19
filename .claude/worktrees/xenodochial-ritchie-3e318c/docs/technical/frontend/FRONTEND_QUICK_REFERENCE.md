# Quick Reference: Frontend (v2.0 TypeScript)

**Versión**: 2.0
**Fecha**: 2026-02-27

---

## Estructura de un Feature

Cada feature bajo `src/features/<name>/` sigue esta estructura:

```
features/leads/
├── components/       # Componentes TSX
├── hooks/            # Custom hooks (useLeads, etc.)
├── services/         # leads.service.ts — llamadas a la API
├── store/            # leadsStore.ts — Zustand
├── types/            # index.ts — interfaces TypeScript
└── index.ts          # Barrel export
```

---

## API Client

```typescript
import { apiClient } from '@/shared/lib/api-client'

// GET con query params
const res = await apiClient.get<PaginatedResponse<Lead>>('/api/v1/leads', { params: filters })

// POST
const lead = await apiClient.post<Lead>('/api/v1/leads', payload)

// PUT / PATCH / DELETE
await apiClient.put(`/api/v1/leads/${id}`, data)
await apiClient.delete(`/api/v1/leads/${id}`)

// Multipart (CSV upload)
await apiClient.postForm('/api/v1/leads/bulk-import', formData)
```

---

## Zustand Store Pattern

```typescript
import { create } from 'zustand'

interface LeadsState {
  leads: Lead[]
  isLoading: boolean
  setLeads: (leads: Lead[], total: number) => void
}

export const useLeadsStore = create<LeadsState>((set) => ({
  leads: [],
  isLoading: false,
  setLeads: (leads, total) => set({ leads, total }),
}))
```

---

## Permisos

```typescript
import { usePermissions } from '@/shared/hooks/usePermissions'

const { isAdmin, isSuperAdmin, isAgent, canManageCampaigns } = usePermissions()
```

---

## Componentes UI Disponibles

```typescript
// shadcn/ui
import { Button } from '@/shared/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog'
import { Input } from '@/shared/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select'
import { Badge } from '@/shared/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'

// Comunes
import { StatusBadge } from '@/shared/components/common/StatusBadge'
import { ScoreBadge } from '@/shared/components/common/ScoreBadge'
import { DataTable } from '@/shared/components/common/DataTable'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { LoadingSpinner } from '@/shared/components/common/LoadingSpinner'
import { EmptyState } from '@/shared/components/common/EmptyState'
import { ConfirmDialog } from '@/shared/components/common/ConfirmDialog'
```

---

## Toast Notifications

```typescript
import { toast } from 'sonner'

toast.success('Lead creado')
toast.error('Error al guardar')
toast.loading('Guardando...')
```

---

## Constantes de Dominio

```typescript
import {
  PIPELINE_STAGES,       // Array de { key, label }
  PIPELINE_STAGE_CONFIG, // Record<stage, { label, color }>
  LEAD_STATUS_CONFIG,    // Record<status, { label, color }>
  CALIFICACION_CONFIG,   // Record<calificacion, { label, color }>
} from '@/shared/lib/constants'
```

---

## Endpoints del Backend

### Leads
- `GET /api/v1/leads` — lista paginada (params: skip, limit, search, status, calificacion)
- `POST /api/v1/leads` — crear
- `PUT /api/v1/leads/{id}` — actualizar
- `DELETE /api/v1/leads/{id}` — eliminar
- `POST /api/v1/leads/{id}/recalculate-score` — recalcular score
- `POST /api/v1/leads/bulk-import` — importar CSV (multipart)

### Pipeline
- `GET /api/v1/pipeline/stage/{stage}` — leads por etapa
- `POST /api/v1/pipeline/leads/{id}/move` — mover etapa
- `GET /api/v1/pipeline/metrics` — métricas
- `GET /api/v1/pipeline/inactive` — leads inactivos

### Otros
- `GET /api/v1/campaigns` / `POST` / `PUT /{id}` / `DELETE /{id}`
- `GET /api/v1/templates` / `POST` / `PUT /{id}` / `DELETE /{id}`
- `GET /api/v1/appointments` / `POST` / `PUT /{id}` / `DELETE /{id}`
- `GET /api/v1/broker/config` / `PUT /api/v1/broker/prompt-config`
- `GET /api/v1/users` / `POST` / `PUT /{id}` / `DELETE /{id}`
- `GET /api/v1/brokers` (superadmin) / `POST` / `PUT /{id}`

---

## Agregar un Nuevo Feature

1. Crear directorio `src/features/<name>/` con la estructura estándar
2. Definir tipos en `types/index.ts`
3. Crear servicio en `services/<name>.service.ts`
4. Crear store Zustand en `store/<name>Store.ts`
5. Crear componentes TSX en `components/`
6. Exportar desde `index.ts`
7. Añadir ruta lazy en `src/app/router.tsx`
8. Añadir ítem en `NAV_ITEMS` de `src/shared/components/layout/Sidebar.tsx`
