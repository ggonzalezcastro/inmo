import { apiClient } from '@/shared/lib/api-client'
import type { DLQListResponse } from '../types/dlq.types'

const BASE = '/api/v1/admin/tasks'

export const dlqApi = {
  list: (offset = 0, limit = 50) =>
    apiClient.get<DLQListResponse>(`${BASE}/failed`, { params: { offset, limit } }),

  retry: (id: string) =>
    apiClient.post<{ status: string; id: string }>(`${BASE}/${id}/retry`),

  discard: (id: string) =>
    apiClient.delete<{ status: string; id: string }>(`${BASE}/${id}`),

  bulkRetry: (ids: string[]) =>
    apiClient.post<{ results: Array<{ id: string; status: string }> }>(`${BASE}/bulk-retry`, { ids }),

  bulkDiscard: (ids: string[]) =>
    apiClient.post<{ results: Array<{ id: string; status: string }> }>(`${BASE}/bulk-discard`, { ids }),
}
