import { apiClient } from '@/shared/lib/api-client'
import type { Lead } from '@/features/leads/types'

interface PipelineMetrics {
  stages: Record<string, { count: number; avg_score: number }>
  total: number
  conversion_rate: number
}

export const pipelineService = {
  async getLeadsByStage(stage: string, params: Record<string, unknown> = {}): Promise<Lead[]> {
    const clean = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== null && v !== undefined && v !== '')
    )
    const response = await apiClient.get<{ data: Lead[] } | { leads: Lead[] } | Lead[]>(
      `/api/v1/pipeline/stages/${stage}/leads`,
      { params: clean }
    )
    // Backend returns { stage, data: [...], total, skip, limit }
    if (Array.isArray(response)) return response
    if ('data' in response && Array.isArray(response.data)) return response.data
    if ('leads' in response && Array.isArray(response.leads)) return response.leads
    return []
  },

  async moveLeadToStage(leadId: number, newStage: string, reason = ''): Promise<Lead> {
    return apiClient.post(`/api/v1/pipeline/leads/${leadId}/move-stage`, {
      new_stage: newStage,
      reason,
    })
  },

  async getMetrics(): Promise<PipelineMetrics> {
    return apiClient.get('/api/v1/pipeline/metrics')
  },

  async getInactiveLeads(stage: string, inactivityDays = 7): Promise<Lead[]> {
    return apiClient.get(`/api/v1/pipeline/stages/${stage}/inactive`, {
      params: { inactivity_days: inactivityDays },
    })
  },
}
