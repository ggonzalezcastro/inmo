import { apiClient } from '@/shared/lib/api-client'

export interface Broker {
  id: number
  name: string
  email?: string
  is_active: boolean
  created_at: string
}

export interface CreateBrokerDto {
  name: string
  email?: string
}

export const brokersService = {
  async getAll(): Promise<Broker[]> {
    return apiClient.get('/api/brokers/')
  },

  async create(data: CreateBrokerDto): Promise<Broker> {
    return apiClient.post('/api/brokers/', data)
  },

  async update(id: number, data: Partial<CreateBrokerDto & { is_active: boolean }>): Promise<Broker> {
    return apiClient.put(`/api/brokers/${id}`, data)
  },

  async delete(id: number): Promise<void> {
    return apiClient.delete(`/api/brokers/${id}`)
  },
}
