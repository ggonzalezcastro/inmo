import { apiClient } from '@/shared/lib/api-client'
import type { BrokerPlan, PlanCreate } from '../types/plans.types'

export const plansApi = {
  list: () => apiClient.get<BrokerPlan[]>('/api/v1/admin/plans'),

  create: (data: PlanCreate) =>
    apiClient.post<BrokerPlan>('/api/v1/admin/plans', data),

  update: (id: number, data: Partial<PlanCreate> & { is_active?: boolean }) =>
    apiClient.put<BrokerPlan>(`/api/v1/admin/plans/${id}`, data),

  deactivate: (id: number) =>
    apiClient.delete<{ status: string }>(`/api/v1/admin/plans/${id}`),

  assignToBroker: (brokerId: number, planId: number | null) =>
    apiClient.put(`/api/v1/admin/brokers/${brokerId}/plan`, { plan_id: planId }),
}
