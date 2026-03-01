export type UserRole = 'superadmin' | 'admin' | 'agent'

export interface AuthUser {
  id: number
  email: string
  name: string
  role: UserRole
  broker_id: number | null
  is_active: boolean
}

export interface JWTPayload {
  sub: string
  email: string
  role: string
  broker_id: number | null
  exp: number
}

export interface LoginCredentials {
  email: string
  password: string
}

export interface RegisterData {
  email: string
  password: string
  broker_name: string
}
