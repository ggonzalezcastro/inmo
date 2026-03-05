import { apiClient } from '@/shared/lib/api-client'

export interface ConversationLead {
  id: number
  name: string | null
  phone: string
  pipeline_stage: string | null
  status: string | null
  human_mode: boolean
  human_assigned_to: number | null
  last_message: string | null
  last_message_at: string | null
  last_message_direction: 'in' | 'out' | null
  channel: string | null
  unread_count: number
}

export const conversationService = {
  async list(mode?: 'human' | 'ai', search?: string): Promise<ConversationLead[]> {
    const params: Record<string, string> = {}
    if (mode) params.mode = mode
    if (search) params.search = search
    return apiClient.get<ConversationLead[]>('/api/v1/conversations', { params })
  },

  async takeover(leadId: number): Promise<void> {
    await apiClient.post(`/api/v1/conversations/leads/${leadId}/takeover`)
  },

  async release(leadId: number): Promise<void> {
    await apiClient.post(`/api/v1/conversations/leads/${leadId}/release`)
  },

  async sendMessage(leadId: number, text: string): Promise<void> {
    await apiClient.post(`/api/v1/conversations/leads/${leadId}/human-message`, { text })
  },
}
