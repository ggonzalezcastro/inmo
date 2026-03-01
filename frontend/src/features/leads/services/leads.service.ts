import { apiClient } from '@/shared/lib/api-client'
import type { PaginatedResponse } from '@/shared/types/api'
import type { Lead, LeadFilters, CreateLeadDto, UpdateLeadDto } from '../types'

export const leadsService = {
  async getLeads(filters: Partial<LeadFilters> = {}): Promise<PaginatedResponse<Lead>> {
    // Remove empty/undefined values
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v !== '' && v !== undefined && v !== null)
    )
    return apiClient.get('/api/v1/leads', { params })
  },

  async getLead(id: number): Promise<Lead> {
    return apiClient.get(`/api/v1/leads/${id}`)
  },

  async createLead(data: CreateLeadDto): Promise<Lead> {
    return apiClient.post('/api/v1/leads', data)
  },

  async updateLead(id: number, data: UpdateLeadDto): Promise<Lead> {
    return apiClient.put(`/api/v1/leads/${id}`, data)
  },

  async deleteLead(id: number): Promise<void> {
    return apiClient.delete(`/api/v1/leads/${id}`)
  },

  async assignLead(id: number, agentId: number): Promise<Lead> {
    return apiClient.put(`/api/v1/leads/${id}/assign`, { agent_id: agentId })
  },

  async movePipeline(id: number, stage: string): Promise<Lead> {
    return apiClient.put(`/api/v1/leads/${id}/pipeline`, { stage })
  },

  async recalculateScore(id: number): Promise<{ lead_score: number; qualification: string }> {
    return apiClient.post(`/api/v1/leads/${id}/recalculate`)
  },

  async bulkImport(file: File): Promise<{ imported: number; errors: number }> {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.postForm('/api/v1/leads/bulk-import', formData)
  },
}
