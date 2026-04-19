export type CalendarViewType = 'dayGridMonth' | 'timeGridWeek' | 'timeGridDay' | 'listWeek'

export type CalendarProvider = 'internal' | 'google' | 'outlook'

export type AppointmentStatus = 'scheduled' | 'confirmed' | 'cancelled' | 'completed' | 'no_show'

export type AppointmentTypeEnum =
  | 'property_visit'
  | 'virtual_meeting'
  | 'phone_call'
  | 'office_meeting'
  | 'other'

export interface CalendarEventExtendedProps {
  appointmentId: number
  leadId: number
  leadName: string
  leadPhone?: string
  agentId?: number
  agentName?: string
  status: AppointmentStatus
  appointmentType: AppointmentTypeEnum
  provider: CalendarProvider
  notes?: string
  meetUrl?: string
  location?: string
  propertyAddress?: string
  cancellationReason?: string
  durationMinutes: number
}

export interface CalendarEvent {
  id: string
  title: string
  start: string
  end: string
  extendedProps: CalendarEventExtendedProps
  backgroundColor: string
  borderColor: string
  textColor: string
  editable: boolean
}

export interface CalendarFilters {
  agentId?: number
  status?: AppointmentStatus | ''
  provider?: CalendarProvider | ''
  dateStart?: string
  dateEnd?: string
}

export interface CalendarConnection {
  provider: CalendarProvider
  connected: boolean
  email?: string
  calendarId?: string
}

export interface CreateAppointmentPayload {
  lead_id: number
  agent_id?: number
  appointment_type: AppointmentTypeEnum
  start_time: string
  duration_minutes: number
  location?: string
  property_address?: string
  notes?: string
  lead_notes?: string
}

export interface UpdateAppointmentPayload {
  appointment_type?: AppointmentTypeEnum
  start_time?: string
  duration_minutes?: number
  agent_id?: number
  location?: string
  property_address?: string
  notes?: string
  lead_notes?: string
  status?: AppointmentStatus
}

export interface ReschedulePayload {
  start_time: string
  duration_minutes: number
}

/** Raw appointment shape returned by the backend */
export interface AppointmentResponse {
  id: number
  lead_id: number
  lead_name?: string
  lead_phone?: string
  agent_id?: number
  agent_name?: string
  appointment_type: AppointmentTypeEnum
  status: AppointmentStatus
  start_time: string
  end_time: string
  duration_minutes: number
  location?: string
  property_address?: string
  meet_url?: string
  notes?: string
  lead_notes?: string
  cancellation_reason?: string
  cancelled_at?: string
  broker_id: number
  created_at: string
  updated_at: string
}
