import { apiClient } from '@/shared/lib/api-client'

export interface ChatMessage {
  id: number
  direction: 'in' | 'out'
  message_text: string
  sender_type: 'customer' | 'bot'
  created_at: string | null
  ai_response_used: boolean
  provider?: string
}

interface ChatMessagesResponse {
  lead_id: number
  provider: string
  messages: ChatMessage[]
  total: number
  skip: number
  limit: number
}

export const chatService = {
  async getMessages(leadId: number, limit = 100): Promise<ChatMessage[]> {
    const res = await apiClient.get<ChatMessagesResponse>(
      `/api/v1/chat/${leadId}/messages`,
      { params: { limit } }
    )
    return res.messages ?? []
  },
}
