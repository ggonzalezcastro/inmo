import { apiClient } from '@/shared/lib/api-client'

export interface ProviderConfigs {
  whatsapp?: {
    phone_number_id?: string
    access_token?: string
    app_secret?: string
  }
  telegram?: {
    bot_token?: string
    webhook_secret?: string
  }
  [key: string]: Record<string, string | undefined> | undefined
}

export interface ChatConfigResponse {
  broker_id: number
  enabled_providers: string[]
  default_provider: string
  provider_configs: ProviderConfigs
  webhook_configs: Record<string, { url: string; enabled: boolean; registered_at?: string }>
}

export interface ChatConfigUpdate {
  enabled_providers: string[]
  provider_configs: ProviderConfigs
}

export const chatConfigService = {
  async get(brokerId: number): Promise<ChatConfigResponse> {
    return apiClient.get(`/api/v1/admin/brokers/${brokerId}/chat-config`)
  },

  async update(brokerId: number, data: ChatConfigUpdate): Promise<ChatConfigResponse> {
    return apiClient.put(`/api/v1/admin/brokers/${brokerId}/chat-config`, data)
  },

  async registerWebhook(brokerId: number): Promise<{ ok: boolean; webhook_url: string }> {
    return apiClient.post(`/api/v1/admin/brokers/${brokerId}/chat-config/register-webhook`)
  },
}
