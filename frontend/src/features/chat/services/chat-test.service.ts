import { apiClient } from '@/shared/lib/api-client'

export interface LastAnalysis {
  qualified?: 'yes' | 'no' | 'maybe'
  interest_level?: number
  timeline?: string
  name?: string
  phone?: string
  email?: string
  salary?: number
  location?: string
  dicom_status?: 'clean' | 'has_debt' | null
  morosidad_amount?: number
  key_points?: string[]
  score_delta?: number
}

export interface DebugInfo {
  conversation_state?: string
  last_analysis?: LastAnalysis
  key_points?: string[]
  conversation_summary?: string
  human_mode?: boolean
  pipeline_stage?: string
}

export interface ChatTestResponse {
  response: string
  lead_id: number
  lead_score: number
  lead_status: string
  debug_info?: DebugInfo
}

export interface CapturedData {
  name: string | null
  phone: string | null
  email: string | null
  budget: string | null
  location: string | null
  timeline: string | null
  property_type: string | null
  rooms: string | number | null
  monthly_income: number | null
  dicom_status: 'clean' | 'has_debt' | 'unknown' | null
  morosidad_amount: number | null
}

export const emptyCapturedData: CapturedData = {
  name: null,
  phone: null,
  email: null,
  budget: null,
  location: null,
  timeline: null,
  property_type: null,
  rooms: null,
  monthly_income: null,
  dicom_status: null,
  morosidad_amount: null,
}

interface LeadApiResponse {
  id: number
  name?: string
  phone?: string
  email?: string
  lead_score?: number
  status?: string
  lead_metadata?: Record<string, unknown>
  metadata?: Record<string, unknown>
  tags?: string[]
  pipeline_stage?: string
}

function isFakePhone(phone: string, lead: LeadApiResponse): boolean {
  if (!phone) return true
  if (phone.startsWith('telegram_')) return true
  if (phone.startsWith('web_chat_')) return true
  if (phone.startsWith('whatsapp_')) return true
  if (phone.startsWith('+569999')) return true
  if (lead.name === 'Test User' && lead.tags?.includes('test')) {
    const digits = phone.replace('+569', '')
    if (digits.length === 8) {
      const uniqueDigits = new Set(digits.split(''))
      if (uniqueDigits.size <= 2) return true
    }
  }
  return false
}

export async function sendTestMessage(
  message: string,
  leadId: number | null
): Promise<ChatTestResponse> {
  return apiClient.post<ChatTestResponse>('/api/v1/chat/test', {
    message,
    lead_id: leadId,
  })
}

export async function fetchLeadDebugData(leadId: number): Promise<{ capturedData: CapturedData }> {
  const lead = await apiClient.get<LeadApiResponse>(`/api/v1/leads/${leadId}`)
  const metadata = (lead.lead_metadata || lead.metadata || {}) as Record<string, unknown>
  const lastAnalysis = (metadata.last_analysis || {}) as Record<string, unknown>

  let phone = lead.phone || null
  if (phone && isFakePhone(phone, lead)) phone = null
  if (!phone && lastAnalysis.phone) phone = lastAnalysis.phone as string

  let name = lead.name || null
  if (name === 'Test User' || name === 'User') name = null
  if (!name && lastAnalysis.name) name = lastAnalysis.name as string

  let email = lead.email || null
  if (!email && lastAnalysis.email) email = lastAnalysis.email as string

  const budget =
    (metadata.budget || metadata.presupuesto || lastAnalysis.budget) as string | null ?? null
  const location =
    (metadata.location || metadata.ubicacion || lastAnalysis.location) as string | null ?? null
  const timeline =
    (metadata.timeline || metadata.tiempo || lastAnalysis.timeline) as string | null ?? null
  const property_type =
    (metadata.property_type || metadata.tipo_inmueble || lastAnalysis.property_type) as string | null ?? null
  const rooms =
    (metadata.rooms || metadata.habitaciones || lastAnalysis.rooms) as string | number | null ?? null
  const monthly_income =
    (metadata.monthly_income || metadata.salary || metadata.sueldo ||
      lastAnalysis.salary || lastAnalysis.monthly_income) as number | null ?? null
  const dicom_status =
    (metadata.dicom_status || lastAnalysis.dicom_status) as CapturedData['dicom_status'] ?? null
  const morosidad_amount =
    (metadata.morosidad_amount || lastAnalysis.morosidad_amount) as number | null ?? null

  return {
    capturedData: {
      name,
      phone,
      email,
      budget,
      location,
      timeline,
      property_type,
      rooms,
      monthly_income,
      dicom_status,
      morosidad_amount,
    },
  }
}
