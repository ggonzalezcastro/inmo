import { Component } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore, Login, Register, ProtectedRoute } from './features/auth'
import { Dashboard } from './features/dashboard'
import { LeadsPage } from './features/leads'
import { PipelinePage } from './features/pipeline'
import { CampaignsPage } from './features/campaigns'
import { TemplatesPage } from './features/templates'
import { ChatPage } from './features/chat'
import { SettingsPage } from './features/settings'
import { UsersPage } from './features/users'
import { BrokersPage } from './features/brokers'
import { CostsDashboardPage } from './features/llm-costs'
import ForbiddenPage from './pages/ForbiddenPage'

class ErrorBoundary extends Component {
  state = { hasError: false, error: null }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', fontFamily: 'sans-serif', maxWidth: '600px' }}>
          <h1>Error al cargar la aplicación</h1>
          <p>Revisa la consola del navegador (F12) para más detalles.</p>
          <pre style={{ background: '#f5f5f5', padding: '1rem', overflow: 'auto' }}>
            {this.state.error?.message || 'Error desconocido'}
          </pre>
        </div>
      )
    }
    return this.props.children
  }
}

function PrivateRoute({ children }) {
  const { isLoggedIn } = useAuthStore()
  return isLoggedIn() ? children : <Navigate to="/login" />
}

function App() {
  return (
    <ErrorBoundary>
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
          path="/leads"
          element={
            <PrivateRoute>
              <LeadsPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/pipeline"
          element={
            <PrivateRoute>
              <PipelinePage />
            </PrivateRoute>
          }
        />
        <Route
          path="/campaigns"
          element={
            <PrivateRoute>
              <CampaignsPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/templates"
          element={
            <PrivateRoute>
              <TemplatesPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/chat"
          element={
            <PrivateRoute>
              <ChatPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute allowedRoles={['admin']}>
              <SettingsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/users"
          element={
            <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
              <UsersPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/brokers"
          element={
            <ProtectedRoute allowedRoles={['superadmin']}>
              <BrokersPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/costs"
          element={
            <ProtectedRoute allowedRoles={['admin', 'superadmin']}>
              <CostsDashboardPage />
            </ProtectedRoute>
          }
        />
        <Route path="/403" element={<ForbiddenPage />} />
        <Route path="/" element={<Navigate to="/pipeline" />} />
      </Routes>
    </Router>
    </ErrorBoundary>
  )
}

export default App

