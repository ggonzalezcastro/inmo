import { apiClient } from '@/shared/lib/api-client'
import type { Lead } from '@/features/leads/types'
import { leadsService } from '@/features/leads/services/leads.service'

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
  advised_leads: number
  advised_rate: number
}

export interface ManagementLeadSummary {
  id: number
  name: string
  phone: string
  stage: string
  assigned_to: number | null
  assignee_name: string | null
  source: string
  created_at: string | null
  last_contacted: string | null
  close_reason: string | null
}

export interface ManagementDashboardMetrics {
  period: { date_from: string; date_to: string }
  filters: {
    agents: Array<{ id: number; name: string }>
    projects: Array<{ id: number; name: string }>
    sources: string[]
  }
  commercial: {
    received: number
    assigned: number
    contacted: number
    advised: number
    without_follow_up: number
    first_response_minutes: number | null
    appointments: { scheduled: number; completed: number; cancelled: number; no_show: number }
    reservations: number
    sales: number
    sales_uf: number
    sales_clp: number
    conversion_rate: number
    lead_to_sale_days: number | null
    lost: number
  }
  tasks: {
    created: number
    pending: number
    in_progress: number
    overdue: number
    completed: number
    completion_rate: number
    on_time_rate: number
    avg_resolution_hours: number | null
    avg_delay_hours: number | null
  }
  by_agent: Array<{
    id: number; name: string; leads: number; contacted: number; advised: number
    reservations: number; sales: number; conversion_rate: number
    active_tasks: number; overdue_tasks: number; completed_tasks: number; on_time_rate: number
  }>
  by_project: Array<{ id: number; name: string; deals: number; reservations: number; sales: number; uf: number; clp: number }>
  by_source: Array<{ source: string; leads: number; contacted: number; advised: number; sales: number; conversion_rate: number }>
  lost_reasons: Array<{ reason: string; count: number }>
  trend: Array<{ week: string; label: string; leads: number; advised: number; sales: number; tasks_completed: number }>
  drilldowns: Record<string, { total: number; data: ManagementLeadSummary[] }>
  definitions: Record<string, string>
}

export interface ManagementDashboardFilters {
  broker_id?: number | null
  date_from: string
  date_to: string
  agent_id?: number
  project_id?: number
  source?: string
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

  async getContactabilitySummary(brokerId?: number | null) {
    return leadsService.getContactabilitySummary(brokerId)
  },

  async getManagementMetrics(filters: ManagementDashboardFilters): Promise<ManagementDashboardMetrics> {
    return apiClient.get('/api/v1/pipeline/management-dashboard', {
      params: Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== undefined && value !== null && value !== '')),
    })
  },
}
