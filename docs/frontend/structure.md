# Frontend Architecture

**Date:** Fri Apr 17 2026  
**Project:** Inmo CRM  
**Stack:** React 18 + Vite + TypeScript + Tailwind CSS

---

## 1. Router

Defined in `src/router.tsx`. Uses `createBrowserRouter` from `react-router-dom`.

All protected routes are wrapped with `WebSocketProvider` and `AppShell`.

### 1.1 Public Routes

| Path | Element | Description |
|------|---------|-------------|
| `/login` | `LoginPage` | Authentication |
| `/register` | `RegisterPage` | Registration |
| `/403` | `ForbiddenPage` | Access denied |

### 1.2 Protected Routes

| Path | Element | Guards |
|------|---------|--------|
| `/dashboard` | `DashboardPage` | AuthGuard |
| `/leads` | `LeadsPage` | AuthGuard |
| `/pipeline` | `PipelinePage` | AuthGuard |
| `/campaigns` | `CampaignsPage` | RoleGuard: `admin`, `superadmin` |
| `/properties` | `PropertiesPage` | RoleGuard: `admin`, `superadmin` |
| `/appointments` | `AppointmentsPage` | AuthGuard |
| `/chat` | `ChatPage` | AuthGuard |
| `/conversations` | `ConversationsPage` | AuthGuard |
| `/costs` | `CostsPage` | RoleGuard: `admin`, `superadmin` |
| `/settings` | `SettingsPage` | RoleGuard: `admin`, `superadmin` |
| `/users` | `UsersPage` | RoleGuard: `admin`, `superadmin` |
| `/brokers` | `BrokersPage` | RoleGuard: `superadmin` |
| `/super-admin` | `SuperAdminPage` | RoleGuard: `superadmin` |
| `/admin/observability/*` | `ObservabilityPage` | RoleGuard: `admin`, `superadmin` |
| `*` | `Navigate to="/dashboard"` | Catch-all redirect |

---

## 2. State Management

### 2.1 Auth Store (`authStore.ts`)

Modern Zustand store managing authentication state.

```typescript
interface AuthState {
  user: User | null
  token: string | null
  loading: boolean
  error: string | null
}
```

**Methods:**
- `login()`
- `logout()`
- `register()`
- `fetchUser()`

**Helpers:**
- `isAdmin()` — returns `true` if user role is `admin`
- `isSuperAdmin()` — returns `true` if user role is `superadmin`

### 2.2 Other Stores

| Store | Purpose |
|-------|---------|
| `leadsStore` | Lead list, filters, CRUD operations |
| `pipelineStore` | Pipeline stages, drag-and-drop state |
| `chatStore` | Active chat session, messages |
| `conversationsStore` | Conversation inbox, takeover logic |

---

## 3. WebSocket Context

Defined in `src/shared/context/WebSocketContext.tsx`.

**Connection:**
- Singleton per browser session
- URL: `ws://host/ws/${broker_id}/${user_id}`

**Reconnection:**
- Exponential backoff
- Maximum delay: 30 seconds

**Event Model:**

```typescript
interface WSEvent {
  type: string
  data: any
}
```

**Provider API:**

```typescript
interface WebSocketContextValue {
  subscribe: (fn: (event: WSEvent) => void) => () => void
  connected: boolean
}
```

**Usage:**

```typescript
const { subscribe, connected } = useWebSocket()

useEffect(() => {
  const unsub = subscribe((event) => {
    switch (event.type) {
      case 'new_message':
        // handle
        break
      case 'stage_changed':
        // handle
        break
    }
  })
  return unsub
}, [subscribe])
```

---

## 4. Route Guards

### 4.1 AuthGuard (`AuthGuard.tsx`)

Redirects unauthenticated users to `/login`.

```typescript
<AuthGuard>
  <ProtectedContent />
</AuthGuard>
```

### 4.2 RoleGuard (`RoleGuard.tsx`)

Renders a 403 page if the user's role is not in `allowedRoles`.

```typescript
<RoleGuard allowedRoles={['admin', 'superadmin']}>
  <AdminContent />
</RoleGuard>
```

---

## 5. Shared Components

```
src/shared/
├── components/
│   └── layout/
│       └── AppShell.tsx          # Main layout wrapper (sidebar, header)
├── context/
│   └── WebSocketContext.tsx      # WebSocket connection provider
├── guards/
│   ├── AuthGuard.tsx             # Authentication guard
│   └── RoleGuard.tsx             # Role-based access control
├── lib/
│   └── api.ts                    # Axios instance with interceptors
└── types/
    └── websocket.ts              # WSEvent type definitions
```

### 5.1 AppShell

Wraps protected routes. Provides:
- Sidebar navigation
- Header with user menu
- WebSocket connection lifecycle

### 5.2 API Client (`api.ts`)

Axios instance configured with:
- Base URL from `VITE_API_URL`
- JWT interceptor — adds `Authorization: Bearer <token>` header
- Error interceptor — handles 401 (redirect to login), 403, 500

---

## 6. Feature Structure

Each feature is a self-contained module under `src/features/`.

```
src/features/
├── auth/
│   ├── LoginPage.tsx
│   └── RegisterPage.tsx
├── dashboard/
│   └── DashboardPage.tsx
├── leads/
│   ├── LeadsPage.tsx             # Lead list with filters
│   └── LeadDetailPage.tsx        # Individual lead view
├── pipeline/
│   └── PipelinePage.tsx          # Kanban board
├── campaigns/
│   └── CampaignsPage.tsx         # Campaign management (admin)
├── appointments/
│   └── AppointmentsPage.tsx      # Calendar view
├── chat/
│   └── ChatPage.tsx              # Test chat widget
├── conversations/
│   └── ConversationsPage.tsx     # Inbox with agent takeover
├── settings/
│   └── SettingsPage.tsx          # Broker settings (admin)
├── users/
│   └── UsersPage.tsx             # User management (admin)
├── brokers/
│   └── BrokersPage.tsx           # Broker management (superadmin)
├── llm-costs/
│   └── CostsPage.tsx             # Cost analytics dashboard
├── super-admin/
│   └── SuperAdminPage.tsx        # Superadmin panel
├── observability/
│   └── ObservabilityPage.tsx     # Event/log viewer
└── properties/
    └── PropertiesPage.tsx        # Property listings (admin)
```

---

## 7. API Service

Defined in `src/services/api.ts`. Exports domain-specific API modules.

| Module | Endpoints |
|--------|-----------|
| `authAPI` | `login`, `register` |
| `leadsAPI` | CRUD operations |
| `chatAPI` | `sendMessage` |
| `conversationsAPI` | `takeover`, `release` |
| `appointmentsAPI` | CRUD operations |
| `kbAPI` | Knowledge base queries |
| `costsAPI` | Cost analytics data |

**Usage:**

```typescript
import { leadsAPI } from '@/services/api'

const leads = await leadsAPI.getAll({ brokerId, status })
await leadsAPI.update(id, { stage: 'agendado' })
```

---

## 8. Lazy Loading

All page components are lazy-loaded via `React.lazy` with `React.Suspense`.

**Pattern:**

```typescript
const DashboardPage = lazy(() =>
  import('@/features/dashboard').then(m => ({ default: m.DashboardPage }))
)
```

**Usage in router:**

```typescript
{
  path: '/dashboard',
  element: (
    <Suspense fallback={<PageLoader />}>
      <DashboardPage />
    </Suspense>
  )
}
```

**Benefits:**
- Reduces initial bundle size
- Pages load on demand
- `PageLoader` provides instant feedback during chunk fetch

---

## Changelog

| Date | Change |
|------|--------|
| Fri Apr 17 2026 | Initial draft — documented router, stores, WebSocket, guards, shared components, features, API service, and lazy loading |
