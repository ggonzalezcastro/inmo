import { apiClient } from '@/shared/lib/api-client'
import type { Lead } from '@/features/leads/types'

interface StageMetric {
  count: number
  avg_score: number
}

export interface PipelineMetrics {
  stages: Record<string, StageMetric>
  total: number
  conversion_rate: number
}

export const dashboardService = {
  async getMetrics(): Promise<PipelineMetrics> {
    return apiClient.get('/api/v1/pipeline/metrics')
  },

  async getHotLeads(): Promise<Lead[]> {
    const res = await apiClient.get<unknown>('/api/v1/leads', {
      params: { status: 'hot', limit: 8, skip: 0 },
    })
    if (res && typeof res === 'object' && 'data' in res) {
      return (res as { data: Lead[] }).data ?? []
    }
    return (res as Lead[]) ?? []
  },
}
