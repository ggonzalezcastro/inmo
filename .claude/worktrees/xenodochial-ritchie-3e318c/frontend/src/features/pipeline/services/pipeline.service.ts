import { apiClient } from '@/shared/lib/api-client'
import type { Lead } from '@/features/leads/types'

interface PipelineMetrics {
  stages: Record<string, { count: number; avg_score: number }>
  total: number
  conversion_rate: number
}

export interface FunnelMetrics {
  stage_counts: Record<string, number>
  conversion_rates: Record<string, number>
  avg_stage_days: Record<string, number>
  total_conversion_rate: number
  lost_by_stage: Record<string, number>
  total_leads: number
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

  async moveLeadToStage(
    leadId: number,
    newStage: string,
    closeReason?: string,
    closeReasonDetail?: string,
    reason = ''
  ): Promise<Lead> {
    return apiClient.post(`/api/v1/pipeline/leads/${leadId}/move-stage`, {
      new_stage: newStage,
      reason,
      close_reason: closeReason ?? null,
      close_reason_detail: closeReasonDetail ?? null,
    })
  },

  async assignAgent(leadId: number, agentId: number | null): Promise<void> {
    await apiClient.post(`/api/v1/pipeline/leads/${leadId}/assign`, { agent_id: agentId })
  },

  async listAgents(): Promise<Array<{ id: number; name: string; email: string }>> {
    return apiClient.get('/api/v1/pipeline/agents')
  },

  async getMetrics(): Promise<PipelineMetrics> {
    return apiClient.get('/api/v1/pipeline/metrics')
  },

  async getFunnelMetrics(): Promise<FunnelMetrics> {
    return apiClient.get('/api/v1/pipeline/funnel-metrics')
  },

  async getInactiveLeads(stage: string, inactivityDays = 7): Promise<Lead[]> {
    return apiClient.get(`/api/v1/pipeline/stages/${stage}/inactive`, {
      params: { inactivity_days: inactivityDays },
    })
  },
}
