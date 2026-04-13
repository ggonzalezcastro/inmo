export type CallMode = 'ai_agent' | 'transcriptor' | 'autonomous'

export type CallPurpose =
  | 'calificacion_inicial'
  | 'calificacion_financiera'
  | 'confirmacion_reunion'
  | 'confirmacion_visita'
  | 'seguimiento_post_visita'
  | 'reactivacion'

export const CALL_PURPOSE_LABELS: Record<CallPurpose, string> = {
  calificacion_inicial: 'Calificación inicial',
  calificacion_financiera: 'Calificación financiera',
  confirmacion_reunion: 'Confirmar reunión',
  confirmacion_visita: 'Confirmar visita',
  seguimiento_post_visita: 'Seguimiento post-visita',
  reactivacion: 'Reactivación',
}

export interface CallStartRequest {
  lead_id: number
  call_mode: CallMode
  call_purpose: CallPurpose
}

export interface CallStartResponse {
  voice_call_id: number
  call_mode: CallMode
  // Web SDK modes (ai_agent / transcriptor)
  vapi_public_key: string | null
  vapi_assistant_id: string | null
  assistant_overrides: Record<string, unknown> | null
  vapi_config: Record<string, unknown> | null
  // Autonomous mode: VAPI called the lead directly
  external_call_id: string | null
}

export interface AgentVoiceProfile {
  id: number
  user_id: number
  template_id: number
  selected_voice_id: string | null
  selected_tone: string | null
  assistant_name: string | null
  opening_message: string | null
  preferred_call_mode: CallMode | null
  created_at: string
  updated_at: string | null
}

export interface VoiceEntry {
  voiceId: string
  provider: string
}

export interface AgentVoiceTemplate {
  id: number
  broker_id: number
  name: string
  business_prompt: string | null
  niche_instructions: string | null
  language: string
  max_duration_seconds: number
  max_silence_seconds: number
  recording_policy: 'enabled' | 'optional' | 'disabled'
  // Each entry is either a plain voiceId string (legacy) or a {voiceId, provider} object
  available_voice_ids: (string | VoiceEntry)[]
  available_tones: string[]
  default_call_mode: CallMode
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export interface VapiVoice {
  id: string
  name: string
  provider: string
  language: string | null
  gender: string | null
  preview_url: string | null
}

export type CallState = 'idle' | 'starting' | 'active' | 'ending' | 'ended' | 'error'

export interface TranscriptLine {
  speaker: 'agent' | 'lead' | 'bot'
  text: string
  ts: number
}
