import { apiClient } from '@/shared/lib/api-client'
import type {
  AppointmentResponse,
  CalendarEvent,
  CalendarFilters,
  CreateAppointmentPayload,
  UpdateAppointmentPayload,
  AppointmentStatus,
  AppointmentTypeEnum,
  CalendarProvider,
} from '../types/calendar.types'

// ── Color mapping ─────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<AppointmentStatus, { bg: string; border: string; text: string }> = {
  scheduled: { bg: '#3b82f6', border: '#2563eb', text: '#ffffff' },
  confirmed:  { bg: '#10b981', border: '#059669', text: '#ffffff' },
  cancelled:  { bg: '#f87171', border: '#ef4444', text: '#ffffff' },
  completed:  { bg: '#94a3b8', border: '#64748b', text: '#ffffff' },
  no_show:    { bg: '#f59e0b', border: '#d97706', text: '#ffffff' },
}

export const APPOINTMENT_TYPE_LABELS: Record<AppointmentTypeEnum, string> = {
  property_visit:  'Visita propiedad',
  virtual_meeting: 'Reunión virtual',
  phone_call:      'Llamada',
  office_meeting:  'Reunión en oficina',
  other:           'Otro',
}

export const APPOINTMENT_TYPE_ICONS: Record<AppointmentTypeEnum, string> = {
  property_visit:  '🏠',
  virtual_meeting: '💻',
  phone_call:      '📞',
  office_meeting:  '🏢',
  other:           '📅',
}

// ── Adapter: AppointmentResponse → CalendarEvent ─────────────────────────────

function toCalendarEvent(appt: AppointmentResponse): CalendarEvent {
  const colors = STATUS_COLORS[appt.status]
  const isFinal = appt.status === 'cancelled' || appt.status === 'completed'

  // Determine provider from backend data (google_event_id presence would indicate google/outlook)
  // For now we tag as 'internal'; provider enrichment comes in Sprint 3
  const provider: CalendarProvider = 'internal'

  const typeLabel = APPOINTMENT_TYPE_LABELS[appt.appointment_type] ?? appt.appointment_type
  const leadDisplay = appt.lead_name ?? `Lead #${appt.lead_id}`

  return {
    id: String(appt.id),
    title: `${leadDisplay} — ${typeLabel}`,
    start: appt.start_time,
    end: appt.end_time,
    backgroundColor: colors.bg,
    borderColor: colors.border,
    textColor: colors.text,
    editable: !isFinal,
    extendedProps: {
      appointmentId: appt.id,
      leadId: appt.lead_id,
      leadName: leadDisplay,
      leadPhone: appt.lead_phone,
      agentId: appt.agent_id,
      agentName: appt.agent_name,
      status: appt.status,
      appointmentType: appt.appointment_type,
      provider,
      notes: appt.notes,
      meetUrl: appt.meet_url,
      location: appt.location,
      propertyAddress: appt.property_address,
      cancellationReason: appt.cancellation_reason,
      durationMinutes: appt.duration_minutes,
    },
  }
}

// ── Service ───────────────────────────────────────────────────────────────────

export const calendarService = {
  async fetchEvents(filters: CalendarFilters = {}): Promise<CalendarEvent[]> {
    const params: Record<string, unknown> = {}
    if (filters.agentId)    params.agent_id    = filters.agentId
    if (filters.status)     params.status      = filters.status
    if (filters.dateStart)  params.start_date  = filters.dateStart
    if (filters.dateEnd)    params.end_date    = filters.dateEnd

    const clean = Object.fromEntries(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== '')
    )

    const response = await apiClient.get<
      AppointmentResponse[] | { data: AppointmentResponse[]; total: number }
    >('/api/v1/appointments', { params: clean })

    // Backend returns { data: [...], total, skip, limit }
    const appointments = Array.isArray(response) ? response : response.data
    return appointments.map(toCalendarEvent)
  },

  async createAppointment(payload: CreateAppointmentPayload): Promise<CalendarEvent> {
    const data = await apiClient.post<AppointmentResponse>('/api/v1/appointments', payload)
    return toCalendarEvent(data)
  },

  async updateAppointment(id: number, payload: UpdateAppointmentPayload): Promise<CalendarEvent> {
    const data = await apiClient.put<AppointmentResponse>(`/api/v1/appointments/${id}`, payload)
    return toCalendarEvent(data)
  },

  async rescheduleAppointment(
    id: number,
    newStart: string,
    newEnd: string
  ): Promise<CalendarEvent> {
    // Calculate duration from start/end
    const startMs = new Date(newStart).getTime()
    const endMs = new Date(newEnd).getTime()
    const durationMinutes = Math.round((endMs - startMs) / 60000)

    const data = await apiClient.put<AppointmentResponse>(`/api/v1/appointments/${id}`, {
      start_time: newStart,
      duration_minutes: durationMinutes,
    })
    return toCalendarEvent(data)
  },

  async deleteAppointment(id: number): Promise<void> {
    return apiClient.delete(`/api/v1/appointments/${id}`)
  },

  async confirmAppointment(id: number): Promise<CalendarEvent> {
    const data = await apiClient.post<AppointmentResponse>(`/api/v1/appointments/${id}/confirm`)
    return toCalendarEvent(data)
  },

  async cancelAppointment(id: number, reason?: string): Promise<CalendarEvent> {
    const params = reason ? { reason } : {}
    const data = await apiClient.post<AppointmentResponse>(
      `/api/v1/appointments/${id}/cancel`,
      undefined,
      { params }
    )
    return toCalendarEvent(data)
  },

  async getAvailableSlots(params?: {
    start_date?: string
    end_date?: string
    agent_id?: number
    duration_minutes?: number
  }) {
    return apiClient.get<{ start: string; end: string }[]>(
      '/api/v1/appointments/available/slots',
      { params }
    )
  },
}
