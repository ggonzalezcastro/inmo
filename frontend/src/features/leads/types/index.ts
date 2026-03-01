export type LeadStatus = 'cold' | 'warm' | 'hot' | 'converted' | 'lost'

export type PipelineStage =
  | 'entrada'
  | 'perfilamiento'
  | 'calificacion_financiera'
  | 'agendado'
  | 'seguimiento'
  | 'referidos'
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
  min_score?: number
  max_score?: number
  assigned_to?: number
  skip?: number
  limit?: number
}
