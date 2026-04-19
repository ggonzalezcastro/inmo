import { describe, it, expect, beforeEach } from 'vitest'
import { useAuthStore } from './authStore'

// JWT with payload { sub: "1", email: "test@test.com", role: "admin", broker_id: 42 }
const PAYLOAD = btoa(JSON.stringify({ sub: '1', email: 'test@test.com', role: 'admin', broker_id: 42 }))
  .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')
const MOCK_TOKEN = `eyJhbGciOiJIUzI1NiJ9.${PAYLOAD}.signature`

const MOCK_USER = {
  id: 1,
  email: 'test@test.com',
  name: 'test',
  role: 'admin' as const,
  broker_id: 42,
  is_active: true,
}

beforeEach(() => {
  localStorage.clear()
  useAuthStore.setState({ user: null, token: null, isAuthenticated: false })
})

describe('authStore', () => {
  describe('setAuth', () => {
    it('sets user, token and isAuthenticated', () => {
      useAuthStore.getState().setAuth(MOCK_USER, MOCK_TOKEN)
      const state = useAuthStore.getState()
      expect(state.isAuthenticated).toBe(true)
      expect(state.token).toBe(MOCK_TOKEN)
      expect(state.user?.email).toBe('test@test.com')
    })

    it('persists token to localStorage', () => {
      useAuthStore.getState().setAuth(MOCK_USER, MOCK_TOKEN)
      expect(localStorage.getItem('token')).toBe(MOCK_TOKEN)
    })
  })

  describe('clearAuth', () => {
    it('resets state and removes localStorage keys', () => {
      useAuthStore.getState().setAuth(MOCK_USER, MOCK_TOKEN)
      useAuthStore.getState().clearAuth()
      const state = useAuthStore.getState()
      expect(state.isAuthenticated).toBe(false)
      expect(state.user).toBeNull()
      expect(state.token).toBeNull()
      expect(localStorage.getItem('token')).toBeNull()
      expect(localStorage.getItem('user')).toBeNull()
    })
  })

  describe('isLoggedIn()', () => {
    it('returns false when not authenticated', () => {
      expect(useAuthStore.getState().isLoggedIn()).toBe(false)
    })

    it('returns true after setAuth', () => {
      useAuthStore.getState().setAuth(MOCK_USER, MOCK_TOKEN)
      expect(useAuthStore.getState().isLoggedIn()).toBe(true)
    })
  })

  describe('role helpers', () => {
    it('isAdmin returns true for admin', () => {
      useAuthStore.getState().setAuth(MOCK_USER, MOCK_TOKEN)
      expect(useAuthStore.getState().isAdmin()).toBe(true)
    })

    it('isAdmin returns true for superadmin', () => {
      useAuthStore.getState().setAuth({ ...MOCK_USER, role: 'superadmin' }, MOCK_TOKEN)
      expect(useAuthStore.getState().isAdmin()).toBe(true)
    })

    it('isSuperAdmin returns false for admin', () => {
      useAuthStore.getState().setAuth(MOCK_USER, MOCK_TOKEN)
      expect(useAuthStore.getState().isSuperAdmin()).toBe(false)
    })

    it('getUserRole returns "agent" when not logged in', () => {
      expect(useAuthStore.getState().getUserRole()).toBe('agent')
    })
  })
})
