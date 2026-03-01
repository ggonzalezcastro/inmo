import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { useAuthStore } from '@/features/auth'
import { AuthGuard } from './AuthGuard'

function setAuthenticated(value: boolean) {
  if (value) {
    useAuthStore.setState({
      user: { id: 1, email: 'u@test.com', name: 'u', role: 'agent', broker_id: 1, is_active: true },
      token: 'fake-token',
      isAuthenticated: true,
    })
  } else {
    useAuthStore.setState({ user: null, token: null, isAuthenticated: false })
  }
}

beforeEach(() => setAuthenticated(false))

describe('AuthGuard', () => {
  it('redirects to /login when not authenticated', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/dashboard"
            element={
              <AuthGuard>
                <div>Protected Content</div>
              </AuthGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByText('Login Page')).toBeInTheDocument()
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })

  it('renders children when authenticated', () => {
    setAuthenticated(true)
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/dashboard"
            element={
              <AuthGuard>
                <div>Protected Content</div>
              </AuthGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    )
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
    expect(screen.queryByText('Login Page')).not.toBeInTheDocument()
  })
})
