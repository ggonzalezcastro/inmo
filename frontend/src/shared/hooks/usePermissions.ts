import { useUserRole } from '@/features/auth'

export function usePermissions() {
  const role = useUserRole()

  return {
    role,
    canManageUsers: role === 'admin' || role === 'superadmin',
    canManageBrokers: role === 'superadmin',
    canManageCampaigns: role === 'admin' || role === 'superadmin',
    canConfigureSettings: role === 'admin' || role === 'superadmin',
    canViewAllLeads: role === 'admin' || role === 'superadmin',
    canViewCosts: role === 'admin' || role === 'superadmin',
    isAgent: role === 'agent',
    isAdmin: role === 'admin' || role === 'superadmin',
    isSuperAdmin: role === 'superadmin',
  }
}
