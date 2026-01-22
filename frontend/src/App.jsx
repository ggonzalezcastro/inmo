import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import Login from './components/Login'
import Register from './components/Register'
import Dashboard from './components/Dashboard'
import Leads from './pages/Leads'
import Pipeline from './pages/Pipeline'
import Campaigns from './pages/Campaigns'
import Templates from './pages/Templates'
import Chat from './pages/Chat'
import SettingsPage from './pages/SettingsPage'
import UsersPage from './pages/UsersPage'
import BrokersPage from './pages/BrokersPage'
import ProtectedRoute from './components/ProtectedRoute'

function PrivateRoute({ children }) {
  const { isLoggedIn } = useAuthStore()
  return isLoggedIn() ? children : <Navigate to="/login" />
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
          path="/leads"
          element={
            <PrivateRoute>
              <Leads />
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
          path="/chat"
          element={
            <PrivateRoute>
              <Chat />
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
        <Route path="/" element={<Navigate to="/pipeline" />} />
      </Routes>
    </Router>
  )
}

export default App

