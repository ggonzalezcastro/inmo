import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from '@/shared/components/layout/AppShell'
import { AuthGuard } from '@/shared/guards/AuthGuard'
import { RoleGuard } from '@/shared/guards/RoleGuard'
import { lazy, Suspense } from 'react'
import { LoadingSpinner } from '@/shared/components/common/LoadingSpinner'

// ── Auth (lazy) ─────────────────────────────────────────────────────────────
// Estas páginas son ligeras pero sacarlas del bundle inicial reduce el tiempo
// de parse del chunk principal, beneficiando a usuarios ya autenticados.
const LoginPage = lazy(() =>
  import('@/features/auth/components/LoginPage').then((m) => ({ default: m.LoginPage }))
)
const RegisterPage = lazy(() =>
  import('@/features/auth/components/RegisterPage').then((m) => ({ default: m.RegisterPage }))
)

// ── Feature pages (lazy) ────────────────────────────────────────────────────
const DashboardPage = lazy(() =>
  import('@/features/dashboard').then((m) => ({ default: m.DashboardPage }))
)
const LeadsPage = lazy(() =>
  import('@/features/leads').then((m) => ({ default: m.LeadsPage }))
)
const PipelinePage = lazy(() =>
  import('@/features/pipeline').then((m) => ({ default: m.PipelinePage }))
)
const CampaignsPage = lazy(() =>
  import('@/features/campaigns').then((m) => ({ default: m.CampaignsPage }))
)
const AppointmentsPage = lazy(() =>
  import('@/features/appointments').then((m) => ({ default: m.AppointmentsPage }))
)
const TemplatesPage = lazy(() =>
  import('@/features/templates').then((m) => ({ default: m.TemplatesPage }))
)
const SettingsPage = lazy(() =>
  import('@/features/settings').then((m) => ({ default: m.SettingsPage }))
)
const UsersPage = lazy(() =>
  import('@/features/users').then((m) => ({ default: m.UsersPage }))
)
const BrokersPage = lazy(() =>
  import('@/features/brokers').then((m) => ({ default: m.BrokersPage }))
)
const CostsDashboardPage = lazy(() =>
  import('@/features/llm-costs').then((m) => ({ default: m.CostsDashboardPage }))
)
const ChatPage = lazy(() =>
  import('@/features/chat').then((m) => ({ default: m.ChatPage }))
)

function SuspenseWrapper({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center h-full min-h-[400px]">
          <LoadingSpinner size="lg" />
        </div>
      }
    >
      {children}
    </Suspense>
  )
}

function PrivateLayout() {
  return (
    <AuthGuard>
      <AppShell />
    </AuthGuard>
  )
}

export const router = createBrowserRouter([
  // Public routes
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/403', element: <ForbiddenPage /> },

  // Protected layout
  {
    element: <PrivateLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      {
        path: '/dashboard',
        element: <SuspenseWrapper><DashboardPage /></SuspenseWrapper>,
      },
      {
        path: '/leads',
        element: <SuspenseWrapper><LeadsPage /></SuspenseWrapper>,
      },
      {
        path: '/pipeline',
        element: <SuspenseWrapper><PipelinePage /></SuspenseWrapper>,
      },
      {
        path: '/campaigns',
        element: (
          <RoleGuard allowedRoles={['admin', 'superadmin']}>
            <SuspenseWrapper><CampaignsPage /></SuspenseWrapper>
          </RoleGuard>
        ),
      },
      {
        path: '/appointments',
        element: <SuspenseWrapper><AppointmentsPage /></SuspenseWrapper>,
      },
      {
        path: '/templates',
        element: (
          <RoleGuard allowedRoles={['admin', 'superadmin']}>
            <SuspenseWrapper><TemplatesPage /></SuspenseWrapper>
          </RoleGuard>
        ),
      },
      {
        path: '/chat',
        element: <SuspenseWrapper><ChatPage /></SuspenseWrapper>,
      },
      {
        path: '/costs',
        element: (
          <RoleGuard allowedRoles={['admin', 'superadmin']}>
            <SuspenseWrapper><CostsDashboardPage /></SuspenseWrapper>
          </RoleGuard>
        ),
      },
      {
        path: '/settings',
        element: (
          <RoleGuard allowedRoles={['admin', 'superadmin']}>
            <SuspenseWrapper><SettingsPage /></SuspenseWrapper>
          </RoleGuard>
        ),
      },
      {
        path: '/users',
        element: (
          <RoleGuard allowedRoles={['admin', 'superadmin']}>
            <SuspenseWrapper><UsersPage /></SuspenseWrapper>
          </RoleGuard>
        ),
      },
      {
        path: '/brokers',
        element: (
          <RoleGuard allowedRoles={['superadmin']}>
            <SuspenseWrapper><BrokersPage /></SuspenseWrapper>
          </RoleGuard>
        ),
      },
    ],
  },

  // Catch-all
  { path: '*', element: <Navigate to="/dashboard" replace /> },
])

function ForbiddenPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-slate-900 mb-2">403</h1>
        <p className="text-slate-600 mb-4">No tienes permisos para acceder a esta página.</p>
        <a href="/dashboard" className="text-primary hover:underline">
          Volver al inicio
        </a>
      </div>
    </div>
  )
}
