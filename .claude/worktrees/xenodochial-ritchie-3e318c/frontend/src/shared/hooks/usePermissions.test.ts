import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useAuthStore } from '@/features/auth'
import { usePermissions } from './usePermissions'

function setRole(role: 'agent' | 'admin' | 'superadmin') {
  useAuthStore.setState({
    user: { id: 1, email: 'u@test.com', name: 'u', role, broker_id: 1, is_active: true },
    token: 'fake',
    isAuthenticated: true,
  })
}

beforeEach(() =>
  useAuthStore.setState({ user: null, token: null, isAuthenticated: false })
)

describe('usePermissions', () => {
  it('agent — restricted access', () => {
    setRole('agent')
    const { result } = renderHook(() => usePermissions())
    expect(result.current.isAgent).toBe(true)
    expect(result.current.isAdmin).toBe(false)
    expect(result.current.isSuperAdmin).toBe(false)
    expect(result.current.canManageUsers).toBe(false)
    expect(result.current.canManageBrokers).toBe(false)
    expect(result.current.canManageCampaigns).toBe(false)
    expect(result.current.canViewCosts).toBe(false)
  })

  it('admin — can manage users/campaigns, cannot manage brokers', () => {
    setRole('admin')
    const { result } = renderHook(() => usePermissions())
    expect(result.current.isAdmin).toBe(true)
    expect(result.current.isAgent).toBe(false)
    expect(result.current.isSuperAdmin).toBe(false)
    expect(result.current.canManageUsers).toBe(true)
    expect(result.current.canManageCampaigns).toBe(true)
    expect(result.current.canManageBrokers).toBe(false)
    expect(result.current.canViewCosts).toBe(true)
  })

  it('superadmin — full access', () => {
    setRole('superadmin')
    const { result } = renderHook(() => usePermissions())
    expect(result.current.isSuperAdmin).toBe(true)
    expect(result.current.isAdmin).toBe(true)
    expect(result.current.canManageBrokers).toBe(true)
    expect(result.current.canManageUsers).toBe(true)
  })
})
