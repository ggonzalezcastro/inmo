import { Navigate } from 'react-router-dom'
import { useIsAuthenticated, useUserRole } from '@/features/auth'
import type { UserRole } from '@/shared/types/auth'

interface RoleGuardProps {
  children: React.ReactNode
  allowedRoles: UserRole[]
}

export function RoleGuard({ children, allowedRoles }: RoleGuardProps) {
  const isAuthenticated = useIsAuthenticated()
  const role = useUserRole()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (!role || !allowedRoles.includes(role)) {
    return <Navigate to="/403" replace />
  }

  return <>{children}</>
}
