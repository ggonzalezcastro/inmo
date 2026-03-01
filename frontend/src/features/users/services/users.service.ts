import { apiClient } from '@/shared/lib/api-client'
import type { AuthUser } from '@/shared/types/auth'

export interface CreateUserDto {
  email: string
  password: string
  name?: string
  role: 'admin' | 'agent'
}

export const usersService = {
  async getAll(): Promise<AuthUser[]> {
    return apiClient.get('/api/broker/users')
  },

  async create(data: CreateUserDto): Promise<AuthUser> {
    return apiClient.post('/api/broker/users', data)
  },

  async update(userId: number, data: Partial<CreateUserDto & { is_active: boolean }>): Promise<AuthUser> {
    return apiClient.put(`/api/broker/users/${userId}`, data)
  },

  async delete(userId: number): Promise<void> {
    return apiClient.delete(`/api/broker/users/${userId}`)
  },
}
