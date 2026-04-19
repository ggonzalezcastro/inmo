import { apiClient } from '@/shared/lib/api-client'
import type { Lead } from '@/features/leads/types'

export interface WeeklyTrendPoint {
  week: string
  week_start: string
  count: number
}

export interface PipelineMetrics {
  total_leads: number
  stage_counts: Record<string, number>
  stage_avg_days: Record<string, number>
  /** PIPELINE_STAGES constants dict: stage → description string */
  stages: Record<string, string>
  conversion_rate: number
  weekly_trend: WeeklyTrendPoint[]
  response_rate: number
}

export const dashboardService = {
  async getMetrics(brokerId?: number | null): Promise<PipelineMetrics> {
    return apiClient.get('/api/v1/pipeline/metrics', {
      params: brokerId ? { broker_id: brokerId } : undefined,
    })
  },

  async getHotLeads(brokerId?: number | null): Promise<Lead[]> {
    const params: Record<string, unknown> = { status: 'hot', limit: 8, skip: 0 }
    if (brokerId) params.broker_id = brokerId
    const res = await apiClient.get<unknown>('/api/v1/leads', { params })
    if (res && typeof res === 'object' && 'data' in res) {
      return (res as { data: Lead[] }).data ?? []
    }
    return (res as Lead[]) ?? []
  },
}
