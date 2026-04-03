import { apiClient } from '@/shared/lib/api-client'
import type { AuditLogResponse, AuditLogFilters } from '../types/auditLog.types'

export const auditLogApi = {
  list: (filters: AuditLogFilters) => {
    const params: Record<string, unknown> = { page: filters.page, limit: 50 }
    if (filters.action) params.action = filters.action
    if (filters.resource_type) params.resource_type = filters.resource_type
    if (filters.broker_id) params.broker_id = filters.broker_id
    if (filters.from_date) params.from_date = filters.from_date
    if (filters.to_date) params.to_date = filters.to_date
    return apiClient.get<AuditLogResponse>('/api/v1/admin/audit-log', { params })
  },
}
