import { apiClient } from '@/shared/lib/api-client'

export interface Appointment {
  id: number
  lead_id: number
  agent_id: number | null
  appointment_type: string
  status: 'scheduled' | 'confirmed' | 'cancelled' | 'completed' | 'no_show'
  start_time: string
  end_time: string
  duration_minutes: number
  location: string
  meet_url: string | null
  notes: string | null
}

export interface CreateAppointmentDto {
  lead_id: number
  agent_id: number
  start_time: string
  duration_minutes?: number
  appointment_type?: string
  location?: string
  notes?: string
}

export const appointmentService = {
  async getForLead(leadId: number): Promise<Appointment[]> {
    const res = await apiClient.get<{ data: Appointment[]; total: number }>(
      '/api/v1/appointments',
      { params: { lead_id: leadId, limit: 20 } }
    )
    return res.data
  },

  async create(dto: CreateAppointmentDto): Promise<Appointment> {
    return apiClient.post<Appointment>('/api/v1/appointments', dto)
  },

  async confirm(appointmentId: number): Promise<Appointment> {
    return apiClient.post<Appointment>(`/api/v1/appointments/${appointmentId}/confirm`)
  },

  async cancel(appointmentId: number, reason?: string): Promise<Appointment> {
    const params = reason ? { reason } : {}
    return apiClient.post<Appointment>(`/api/v1/appointments/${appointmentId}/cancel`, null, { params })
  },
}
