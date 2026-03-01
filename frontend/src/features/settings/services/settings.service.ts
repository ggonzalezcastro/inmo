import { apiClient } from '@/shared/lib/api-client'

export interface BrokerConfig {
  id: number
  broker_id: number
  agent_name?: string
  agent_identity?: string
  system_prompt?: string
  rules?: string[]
  few_shot_examples?: Array<{ role: string; content: string }>
  lead_scoring_weights?: Record<string, number>
  score_thresholds?: { cold: number; warm: number; hot: number }
}

export interface PromptPreview {
  system_prompt: string
  token_count?: number
}

export const settingsService = {
  async getConfig(): Promise<BrokerConfig> {
    return apiClient.get('/api/broker/config')
  },

  async updatePromptConfig(data: Partial<BrokerConfig>): Promise<BrokerConfig> {
    return apiClient.put('/api/broker/config/prompt', data)
  },

  async updateLeadConfig(data: Partial<BrokerConfig>): Promise<BrokerConfig> {
    return apiClient.put('/api/broker/config/leads', data)
  },

  async getPromptPreview(): Promise<PromptPreview> {
    return apiClient.get('/api/broker/config/prompt/preview')
  },
}
