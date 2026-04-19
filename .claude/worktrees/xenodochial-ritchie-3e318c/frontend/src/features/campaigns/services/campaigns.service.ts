import { apiClient } from '@/shared/lib/api-client'

export type CampaignStatus = 'draft' | 'pending_review' | 'active' | 'paused' | 'completed'
export type CampaignChannel = 'telegram' | 'whatsapp' | 'call' | 'email'
export type CampaignTrigger = 'manual' | 'lead_score' | 'stage_change' | 'inactivity'
export type StepAction = 'send_message' | 'make_call' | 'update_stage' | 'schedule_meeting'

export interface CampaignStep {
  id: number
  campaign_id: number
  step_number: number
  action: StepAction
  delay_hours: number
  message_template_id?: number
  message_text?: string
  use_ai_message: boolean
  channel?: CampaignChannel
  conditions?: Record<string, unknown>
  target_stage?: string
  created_at: string
  updated_at: string
}

export interface Campaign {
  id: number
  name: string
  description?: string
  channel: CampaignChannel
  status: CampaignStatus
  triggered_by: CampaignTrigger
  trigger_condition?: Record<string, unknown>
  max_contacts?: number
  broker_id: number
  created_by?: number
  approved_by?: number
  steps: CampaignStep[]
  created_at: string
  updated_at: string
}

export interface CampaignListResponse {
  data: Campaign[]
  total: number
  skip: number
  limit: number
}

export interface CampaignStats {
  campaign_id: number
  total_steps: number
  unique_leads: number
  pending: number
  sent: number
  failed: number
  skipped: number
  success_rate: number
  failure_rate: number
}

export interface CreateCampaignDto {
  name: string
  description?: string
  channel: CampaignChannel
  triggered_by?: CampaignTrigger
  trigger_condition?: Record<string, unknown>
  max_contacts?: number
}

export interface CreateStepDto {
  step_number: number
  action: StepAction
  delay_hours: number
  message_template_id?: number
  message_text?: string
  use_ai_message?: boolean
  channel?: CampaignChannel
  conditions?: Record<string, unknown>
  target_stage?: string
}

export const campaignsService = {
  async getAll(params?: { status?: CampaignStatus; channel?: CampaignChannel }): Promise<Campaign[]> {
    const res: CampaignListResponse = await apiClient.get('/api/v1/campaigns', { params })
    return res.data ?? res as unknown as Campaign[]
  },

  async getOne(id: number): Promise<Campaign> {
    return apiClient.get(`/api/v1/campaigns/${id}`)
  },

  async create(data: CreateCampaignDto): Promise<Campaign> {
    return apiClient.post('/api/v1/campaigns', data)
  },

  async update(id: number, data: Partial<CreateCampaignDto & { status: CampaignStatus }>): Promise<Campaign> {
    return apiClient.put(`/api/v1/campaigns/${id}`, data)
  },

  async delete(id: number): Promise<void> {
    return apiClient.delete(`/api/v1/campaigns/${id}`)
  },

  // Approval workflow
  async submitForReview(id: number): Promise<Campaign> {
    return apiClient.put(`/api/v1/campaigns/${id}/submit`)
  },

  async activate(id: number): Promise<Campaign> {
    return apiClient.put(`/api/v1/campaigns/${id}/activate`)
  },

  async pause(id: number): Promise<Campaign> {
    return apiClient.put(`/api/v1/campaigns/${id}/pause`)
  },

  // Steps
  async addStep(campaignId: number, data: CreateStepDto): Promise<CampaignStep> {
    return apiClient.post(`/api/v1/campaigns/${campaignId}/steps`, data)
  },

  async deleteStep(campaignId: number, stepId: number): Promise<void> {
    return apiClient.delete(`/api/v1/campaigns/${campaignId}/steps/${stepId}`)
  },

  async applyToLead(campaignId: number, leadId: number): Promise<void> {
    return apiClient.post(`/api/v1/campaigns/${campaignId}/apply-to-lead/${leadId}`)
  },

  async getStats(id: number): Promise<CampaignStats> {
    return apiClient.get(`/api/v1/campaigns/${id}/stats`)
  },

  async previewMessage(campaignId: number, channel?: CampaignChannel, action?: StepAction): Promise<string> {
    const res: { message: string } = await apiClient.post(`/api/v1/campaigns/${campaignId}/preview-message`, { channel, action })
    return res.message
  },

  async updateStep(campaignId: number, stepId: number, data: Partial<CampaignStepCreate>): Promise<CampaignStep> {
    return apiClient.patch(`/api/v1/campaigns/${campaignId}/steps/${stepId}`, data)
  },

  async getMatchingLeads(campaignId: number): Promise<{ trigger: string; total: number; note: string; leads: { id: number; name: string; score?: number }[] }> {
    return apiClient.get(`/api/v1/campaigns/${campaignId}/matching-leads`)
  },
}
