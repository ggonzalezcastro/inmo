import { apiClient } from '@/shared/lib/api-client'
import type { AuthUser, LoginCredentials, RegisterData } from '@/shared/types/auth'

interface LoginResponse {
  access_token: string
}

interface RegisterResponse {
  access_token: string
}

export const authService = {
  async login(credentials: LoginCredentials): Promise<LoginResponse> {
    return apiClient.post<LoginResponse>('/auth/login', credentials)
  },

  async register(data: RegisterData): Promise<RegisterResponse> {
    return apiClient.post<RegisterResponse>('/auth/register', data)
  },

  async getCurrentUser(): Promise<AuthUser> {
    return apiClient.get<AuthUser>('/auth/me')
  },
}
