import { create } from 'zustand'
import type { AuthUser, JWTPayload } from '@/shared/types/auth'
import { setTokenGetter } from '@/shared/lib/api-client'

interface AuthState {
  user: AuthUser | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean

  // Impersonation
  isImpersonating: boolean
  originalToken: string | null
  impersonatedBrokerName: string | null

  setAuth: (user: AuthUser, token: string) => void
  clearAuth: () => void
  updateUser: (updates: Partial<AuthUser>) => void
  isLoggedIn: () => boolean
  getUserRole: () => string
  isAdmin: () => boolean
  isSuperAdmin: () => boolean

  startImpersonation: (token: string, brokerName: string) => void
  exitImpersonation: () => void
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
    const parsed = storedUserRaw ? (JSON.parse(storedUserRaw) as AuthUser) : tokenToUser(storedToken)
    // Normalize role to lowercase in case it was stored with uppercase (backend returns ADMIN/AGENT)
    initialUser = parsed ? { ...parsed, role: (parsed.role?.toLowerCase() as AuthUser['role']) || 'agent' } : null
  } catch {
    initialUser = tokenToUser(storedToken)
  }
}

// Rehydrate impersonation session from sessionStorage (survives page refresh, not tab close)
function _isTokenAlive(token: string): boolean {
  const payload = decodeJWT(token)
  if (!payload) return false
  return payload.exp > Math.floor(Date.now() / 1000)
}

const _storedOriginalToken = sessionStorage.getItem('originalToken')
const _storedBrokerName = sessionStorage.getItem('impersonatedBrokerName')
let initialIsImpersonating = false
let initialOriginalToken: string | null = null
let initialImpersonatedBrokerName: string | null = null

if (_storedOriginalToken && _isTokenAlive(_storedOriginalToken)) {
  initialIsImpersonating = true
  initialOriginalToken = _storedOriginalToken
  initialImpersonatedBrokerName = _storedBrokerName
} else if (_storedOriginalToken) {
  // Original token expired — clean up stale sessionStorage silently
  sessionStorage.removeItem('originalToken')
  sessionStorage.removeItem('impersonatedBrokerName')
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: initialUser,
  token: initialToken,
  isAuthenticated: !!initialToken,
  isLoading: false,
  isImpersonating: initialIsImpersonating,
  originalToken: initialOriginalToken,
  impersonatedBrokerName: initialImpersonatedBrokerName,

  setAuth: (user, token) => {
    // Normalize role to lowercase — backend returns ADMIN/AGENT (uppercase)
    const normalized: AuthUser = { ...user, role: (user.role?.toLowerCase() as AuthUser['role']) || 'agent' }
    // Keep localStorage in sync so the legacy api.js interceptor works (ChatTest.jsx)
    localStorage.setItem('token', token)
    localStorage.setItem('user', JSON.stringify(normalized))
    setTokenGetter(() => token)
    set({ user: normalized, token, isAuthenticated: true })
  },

  clearAuth: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    sessionStorage.removeItem('originalToken')
    sessionStorage.removeItem('impersonatedBrokerName')
    setTokenGetter(() => null)
    set({ user: null, token: null, isAuthenticated: false, isImpersonating: false, originalToken: null, impersonatedBrokerName: null })
  },

  updateUser: (updates) => {
    const current = get().user
    if (!current) return
    const updated = { ...current, ...updates }
    localStorage.setItem('user', JSON.stringify(updated))
    set({ user: updated })
  },

  startImpersonation: (token: string, brokerName: string) => {
    const originalToken = get().token
    const impersonatedUser = tokenToUser(token)
    if (!impersonatedUser) return

    // Persist to sessionStorage so impersonation survives a page refresh
    if (originalToken) sessionStorage.setItem('originalToken', originalToken)
    sessionStorage.setItem('impersonatedBrokerName', brokerName)

    // Update token in storage and apiClient (without overwriting the original user)
    localStorage.setItem('token', token)
    setTokenGetter(() => token)
    set({
      token,
      user: impersonatedUser,
      isImpersonating: true,
      originalToken,
      impersonatedBrokerName: brokerName,
    })
  },

  exitImpersonation: () => {
    // Fallback to sessionStorage in case Zustand state was lost after a page refresh
    const original = get().originalToken ?? sessionStorage.getItem('originalToken')
    if (!original || !_isTokenAlive(original)) {
      // Token missing or expired during impersonation — force re-login
      sessionStorage.removeItem('originalToken')
      sessionStorage.removeItem('impersonatedBrokerName')
      get().clearAuth()
      return
    }

    const originalUser = tokenToUser(original)
    localStorage.setItem('token', original)
    if (originalUser) localStorage.setItem('user', JSON.stringify(originalUser))
    setTokenGetter(() => original)

    sessionStorage.removeItem('originalToken')
    sessionStorage.removeItem('impersonatedBrokerName')

    set({
      token: original,
      user: originalUser,
      isImpersonating: false,
      originalToken: null,
      impersonatedBrokerName: null,
    })
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
