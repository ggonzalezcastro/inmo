import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import Login from './components/Login'
import Register from './components/Register'
import Dashboard from './components/Dashboard'
import Pipeline from './pages/Pipeline'
import Campaigns from './pages/Campaigns'
import Templates from './pages/Templates'

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
        <Route path="/" element={<Navigate to="/dashboard" />} />
      </Routes>
    </Router>
  )
}

export default App

