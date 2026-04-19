export type LeadStatus = 'cold' | 'warm' | 'hot' | 'converted' | 'lost'

export type PipelineStage =
  | 'entrada'
  | 'perfilamiento'
  | 'calificacion_financiera'
  | 'potencial'
  | 'agendado'
  | 'ganado'
  | 'perdido'

export type LeadCalificacion = 'CALIFICADO' | 'POTENCIAL' | 'NO_CALIFICADO'

export interface LeadMetadata {
  location?: string
  budget?: string
  property_type?: string
  timeline?: string
  monthly_income?: number
  dicom_status?: 'clean' | 'has_debt' | 'unknown'
  morosidad_amount?: number
  calificacion?: LeadCalificacion
  residency_status?: 'residente' | 'extranjero'
  purpose?: 'vivienda' | 'inversion'
  rooms?: string | number
  [key: string]: unknown
}

export interface NextAppointment {
  id: number
  start_time: string
  status: string
  meet_url: string | null
  appointment_type: string | null
}

export interface Lead {
  id: number
  phone: string
  name: string
  email?: string
  status: LeadStatus
  lead_score: number
  pipeline_stage: PipelineStage
  lead_metadata: LeadMetadata
  tags: string[]
  assigned_to?: number | null
  broker_id: number
  last_contacted?: string | null
  created_at: string
  updated_at?: string
  next_appointment?: NextAppointment | null
  assigned_agent_name?: string | null
  close_reason?: string | null
  close_reason_detail?: string | null
  response_metrics?: ResponseMetrics | null
}

export interface ResponseMetrics {
  reply_count: number
  avg_response_seconds: number | null
  median_response_seconds: number | null
  fast_reply_count: number
  last_response_seconds: number | null
  is_fast_responder: boolean
  threshold_seconds: number
  min_replies_required: number
  last_computed_at?: string
}

export interface CreateLeadDto {
  phone: string
  name: string
  email?: string
  tags?: string[]
}

export interface UpdateLeadDto {
  name?: string
  email?: string
  phone?: string
  tags?: string[]
  pipeline_stage?: PipelineStage
}

export interface LeadFilters {
  search?: string
  status?: LeadStatus | ''
  pipeline_stage?: PipelineStage | ''
  dicom_status?: 'clean' | 'has_debt' | 'unknown' | ''
  created_from?: string
  created_to?: string
  min_score?: number
  max_score?: number
  assigned_to?: number
  broker_id?: number | null
  skip?: number
  limit?: number
}
