import { apiClient } from '@/shared/lib/api-client'
import type { AuthUser } from '@/shared/types/auth'

export interface CreateUserDto {
  email: string
  password: string
  name?: string
  role: 'admin' | 'agent'
}

export const usersService = {
  async getAll(brokerId?: number | null): Promise<AuthUser[]> {
    const params = brokerId ? { broker_id: brokerId } : undefined
    const res = await apiClient.get<{ users: AuthUser[] } | AuthUser[]>('/api/broker/users', { params })
    // Backend returns { users: [...] }, handle both shapes for safety
    return Array.isArray(res) ? res : (res as { users: AuthUser[] }).users ?? []
  },

  async create(data: CreateUserDto): Promise<AuthUser> {
    const res = await apiClient.post<{ user: AuthUser } | AuthUser>('/api/broker/users', data)
    return (res as { user: AuthUser }).user ?? (res as AuthUser)
  },

  async update(userId: number, data: Partial<CreateUserDto & { is_active: boolean }>): Promise<AuthUser> {
    const res = await apiClient.put<{ user: AuthUser } | AuthUser>(`/api/broker/users/${userId}`, data)
    return (res as { user: AuthUser }).user ?? (res as AuthUser)
  },

  async delete(userId: number): Promise<void> {
    return apiClient.delete(`/api/broker/users/${userId}`)
  },
}
