import { apiClient } from '@/shared/lib/api-client'

export type AppointmentStatus = 'scheduled' | 'confirmed' | 'cancelled' | 'completed' | 'no_show'

export interface Appointment {
  id: number
  lead_id: number
  lead_name?: string
  agent_id?: number
  scheduled_at: string
  status: AppointmentStatus
  notes?: string
  meeting_link?: string
  broker_id: number
  created_at: string
}

export interface CreateAppointmentDto {
  lead_id: number
  scheduled_at: string
  notes?: string
}

export interface AppointmentSlot {
  start: string
  end: string
}

export const appointmentsService = {
  async getAll(params: Record<string, unknown> = {}): Promise<Appointment[]> {
    const clean = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== '' && v !== null && v !== undefined)
    )
    return apiClient.get('/api/v1/appointments', { params: clean })
  },

  async create(data: CreateAppointmentDto): Promise<Appointment> {
    return apiClient.post('/api/v1/appointments', data)
  },

  async update(id: number, data: Partial<CreateAppointmentDto>): Promise<Appointment> {
    return apiClient.put(`/api/v1/appointments/${id}`, data)
  },

  async delete(id: number): Promise<void> {
    return apiClient.delete(`/api/v1/appointments/${id}`)
  },

  async confirm(id: number): Promise<Appointment> {
    return apiClient.post(`/api/v1/appointments/${id}/confirm`)
  },

  async cancel(id: number): Promise<Appointment> {
    return apiClient.post(`/api/v1/appointments/${id}/cancel`)
  },

  async getAvailableSlots(): Promise<AppointmentSlot[]> {
    return apiClient.get('/api/v1/appointments/available/slots')
  },
}
