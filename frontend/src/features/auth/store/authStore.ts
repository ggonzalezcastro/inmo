import { create } from 'zustand'
import type { AuthUser, JWTPayload } from '@/shared/types/auth'
import { setTokenGetter } from '@/shared/lib/api-client'

interface AuthState {
  user: AuthUser | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean

  setAuth: (user: AuthUser, token: string) => void
  clearAuth: () => void
  updateUser: (updates: Partial<AuthUser>) => void
  isLoggedIn: () => boolean
  getUserRole: () => string
  isAdmin: () => boolean
  isSuperAdmin: () => boolean
}

function decodeJWT(token: string): JWTPayload | null {
  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload) as JWTPayload
  } catch {
    return null
  }
}

function tokenToUser(token: string, fallbackEmail = ''): AuthUser | null {
  const payload = decodeJWT(token)
  if (!payload) return null
  return {
    id: parseInt(payload.sub),
    email: payload.email || fallbackEmail,
    name: payload.email?.split('@')[0] || 'Usuario',
    role: (payload.role?.toLowerCase() as AuthUser['role']) || 'agent',
    broker_id: payload.broker_id ?? null,
    is_active: true,
  }
}

// Rehydrate from localStorage on startup (backward compat with ChatTest.jsx api.js)
const storedToken = localStorage.getItem('token')
const storedUserRaw = localStorage.getItem('user')
let initialUser: AuthUser | null = null
let initialToken: string | null = null

if (storedToken) {
  initialToken = storedToken
  try {
    initialUser = storedUserRaw ? (JSON.parse(storedUserRaw) as AuthUser) : tokenToUser(storedToken)
  } catch {
    initialUser = tokenToUser(storedToken)
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: initialUser,
  token: initialToken,
  isAuthenticated: !!initialToken,
  isLoading: false,

  setAuth: (user, token) => {
    // Keep localStorage in sync so the legacy api.js interceptor works (ChatTest.jsx)
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(user))
    setTokenGetter(() => token)
    set({ user, token, isAuthenticated: true })
  },

  clearAuth: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    setTokenGetter(() => null)
    set({ user: null, token: null, isAuthenticated: false })
  },

  updateUser: (updates) => {
    const current = get().user
    if (!current) return
    const updated = { ...current, ...updates }
    localStorage.setItem('user', JSON.stringify(updated))
    set({ user: updated })
  },

  // Legacy interface for backward compat with old components (ChatTest uses this)
  isLoggedIn: () => get().isAuthenticated,
  getUserRole: () => get().user?.role ?? 'agent',
  isAdmin: () => {
    const role = get().user?.role
    return role === 'admin' || role === 'superadmin'
  },
  isSuperAdmin: () => get().user?.role === 'superadmin',
}))

// Initialize token getter
if (initialToken) {
  setTokenGetter(() => useAuthStore.getState().token)
}

// Selectors
export const useAuthUser = () => useAuthStore((s) => s.user)
export const useIsAuthenticated = () => useAuthStore((s) => s.isAuthenticated)
export const useUserRole = () => useAuthStore((s) => s.user?.role)
export const useAuthToken = () => useAuthStore((s) => s.token)

// Helper re-export for tokenToUser (used in services)
export { tokenToUser, decodeJWT }
