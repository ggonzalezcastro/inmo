import { apiClient } from '@/shared/lib/api-client'

export interface Template {
  id: number
  name: string
  content: string
  channel: 'telegram' | 'whatsapp' | 'call' | 'email'
  agent_type: string
  broker_id: number
  variables?: string[]
}

export interface CreateTemplateDto {
  name: string
  content: string
  channel: string
  agent_type: string
}

export const templatesService = {
  async getAll(params: Record<string, unknown> = {}): Promise<Template[]> {
    return apiClient.get('/api/v1/templates', { params })
  },

  async getOne(id: number): Promise<Template> {
    return apiClient.get(`/api/v1/templates/${id}`)
  },

  async create(data: CreateTemplateDto): Promise<Template> {
    return apiClient.post('/api/v1/templates', data)
  },

  async update(id: number, data: Partial<CreateTemplateDto>): Promise<Template> {
    return apiClient.put(`/api/v1/templates/${id}`, data)
  },

  async delete(id: number): Promise<void> {
    return apiClient.delete(`/api/v1/templates/${id}`)
  },

  async getByAgentType(agentType: string, channel?: string): Promise<Template[]> {
    return apiClient.get(`/api/v1/templates/agent-type/${agentType}`, {
      params: channel ? { channel } : {},
    })
  },
}
