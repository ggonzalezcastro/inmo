import { apiClient } from '@/shared/lib/api-client'
import type { DashboardKPIs, SystemHealth } from '../types/superAdmin.types'

export const superAdminApi = {
  getDashboard: () =>
    apiClient.get<DashboardKPIs>('/api/v1/admin/dashboard'),

  getHealth: () =>
    apiClient.get<SystemHealth>('/api/v1/admin/health'),
}
