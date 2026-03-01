import { apiClient } from '@/shared/lib/api-client'

export interface CampaignStep {
  id: number
  action: string
  delay_minutes: number
  template_id?: number
  order: number
}

export interface Campaign {
  id: number
  name: string
  description?: string
  status: 'active' | 'inactive' | 'draft'
  broker_id: number
  steps?: CampaignStep[]
  stats?: CampaignStats
}

export interface CampaignStats {
  total_sent: number
  total_failed: number
  success_rate: number
}

export interface CreateCampaignDto {
  name: string
  description?: string
}

export interface CreateStepDto {
  action: string
  delay_minutes: number
  template_id?: number
  order?: number
}

export const campaignsService = {
  async getAll(): Promise<Campaign[]> {
    return apiClient.get('/api/v1/campaigns')
  },

  async getOne(id: number): Promise<Campaign> {
    return apiClient.get(`/api/v1/campaigns/${id}`)
  },

  async create(data: CreateCampaignDto): Promise<Campaign> {
    return apiClient.post('/api/v1/campaigns', data)
  },

  async update(id: number, data: Partial<CreateCampaignDto>): Promise<Campaign> {
    return apiClient.put(`/api/v1/campaigns/${id}`, data)
  },

  async delete(id: number): Promise<void> {
    return apiClient.delete(`/api/v1/campaigns/${id}`)
  },

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
}
