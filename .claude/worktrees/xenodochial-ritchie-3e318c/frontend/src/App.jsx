import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { useAuthStore } from './store/authStore'
import Login from './components/Login'
import Register from './components/Register'
import Dashboard from './components/Dashboard'
import Pipeline from './pages/Pipeline'
import Campaigns from './pages/Campaigns'
import Templates from './pages/Templates'
import SettingsPage from './pages/SettingsPage'

const ObservabilityPage = lazy(() =>
  import('./features/observability').then(m => ({ default: m.ObservabilityPage }))
)

function PrivateRoute({ children }) {
  const { isLoggedIn } = useAuthStore()
  return isLoggedIn() ? children : <Navigate to="/login" />
}

function SuperAdminRoute({ children }) {
  const { isLoggedIn } = useAuthStore()
  if (!isLoggedIn()) return <Navigate to="/login" />
  // Decode role from the JWT payload.
  // JWT uses base64url encoding: replace - with + and _ with / before atob().
  try {
    const token = localStorage.getItem('token') || ''
    const b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const payload = JSON.parse(atob(b64))
    const role = (payload?.role || '').toUpperCase()
    if (role !== 'SUPERADMIN' && role !== 'ADMIN') return <Navigate to="/dashboard" />
  } catch {
    return <Navigate to="/login" />
  }
  return children
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/dashboard"
          element={
            <PrivateRoute>
              <Dashboard />
            </PrivateRoute>
          }
        />
        <Route
          path="/pipeline"
          element={
            <PrivateRoute>
              <Pipeline />
            </PrivateRoute>
          }
        />
        <Route
          path="/campaigns"
          element={
            <PrivateRoute>
              <Campaigns />
            </PrivateRoute>
          }
        />
        <Route
          path="/templates"
          element={
            <PrivateRoute>
              <Templates />
            </PrivateRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <PrivateRoute>
              <SettingsPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/admin/observability/*"
          element={
            <SuperAdminRoute>
              <Suspense fallback={<div className="p-8 text-slate-500">Cargando…</div>}>
                <ObservabilityPage />
              </Suspense>
            </SuperAdminRoute>
          }
        />
        <Route path="/" element={<Navigate to="/dashboard" />} />
      </Routes>
    </Router>
  )
}

export default App

