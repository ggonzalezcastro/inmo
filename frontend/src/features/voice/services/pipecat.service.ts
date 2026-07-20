import { apiClient } from '@/shared/lib/api-client'
import type { CallPurpose } from '../types'

export type PipecatMode = 'autonomous' | 'copilot' | 'handoff' | 'coaching'

export interface PipecatCallResponse {
  voice_call_id: number
  pipecat_mode: PipecatMode
  status: string
}

export interface TranscriptLine {
  speaker: 'customer' | 'bot' | 'agent'
  text: string
  timestamp: string
  emotion_tag_used: string | null
  emotion_detected: string | null
}

export interface CallSummary {
  voice_call_id: number
  summary: string | null
  extracted_data: Record<string, unknown> | null
  call_metrics: Record<string, unknown> | null
  handoff_occurred: boolean
  handoff_reason: string | null
}

export interface CallListItem {
  id: number
  lead_id: number
  lead_name: string | null
  lead_phone: string | null
  phone_number: string
  status: string
  duration: number | null
  call_purpose: CallPurpose | null
  call_mode: string | null
  pipecat_mode: PipecatMode | null
  handoff_occurred: boolean | null
  summary: string | null
  created_at: string
}

export interface CallListResponse {
  data: CallListItem[]
  total: number
}

export interface CallMetrics {
  total: number
  by_purpose: Record<string, number>
  by_mode: Record<string, number>
  avg_duration_seconds: number | null
  this_month: number
}

export interface CallDetails {
  call: CallListItem & Record<string, unknown>
  transcript_lines: {
    speaker: string
    text: string
    timestamp: number
    confidence: number | null
  }[]
}

export const pipecatService = {
  startAutonomous(leadId: number, purpose?: CallPurpose): Promise<PipecatCallResponse> {
    return apiClient.post('/api/v1/calls/pipecat/autonomous', {
      lead_id: leadId,
      call_purpose: purpose || undefined,
    })
  },

  startCopilot(leadId: number, agentPhone?: string, purpose?: CallPurpose): Promise<PipecatCallResponse> {
    return apiClient.post('/api/v1/calls/pipecat/copilot', {
      lead_id: leadId,
      agent_phone: agentPhone || undefined,
      call_purpose: purpose || undefined,
    })
  },

  startHandoff(leadId: number, agentPhone?: string, purpose?: CallPurpose): Promise<PipecatCallResponse> {
    return apiClient.post('/api/v1/calls/pipecat/handoff', {
      lead_id: leadId,
      agent_phone: agentPhone || undefined,
      call_purpose: purpose || undefined,
    })
  },

  startCoaching(leadId: number, agentPhone?: string, purpose?: CallPurpose): Promise<PipecatCallResponse> {
    return apiClient.post('/api/v1/calls/pipecat/coaching', {
      lead_id: leadId,
      agent_phone: agentPhone || undefined,
      call_purpose: purpose || undefined,
    })
  },

  listCalls(params: { limit?: number; offset?: number; lead_id?: number; purpose?: CallPurpose }): Promise<CallListResponse> {
    return apiClient.get('/api/v1/calls', { params })
  },

  getMetrics(): Promise<CallMetrics> {
    return apiClient.get('/api/v1/calls/metrics')
  },

  getCallDetails(callId: number): Promise<CallDetails> {
    return apiClient.get(`/api/v1/calls/${callId}`)
  },

  endCall(voiceCallId: number): Promise<{ voice_call_id: number; stopped: boolean }> {
    return apiClient.post(`/api/v1/calls/pipecat/${voiceCallId}/end`)
  },

  muteAI(voiceCallId: number): Promise<{ ai_muted: boolean }> {
    return apiClient.post(`/api/v1/calls/pipecat/${voiceCallId}/mute-ai`)
  },

  unmuteAI(voiceCallId: number): Promise<{ ai_muted: boolean }> {
    return apiClient.post(`/api/v1/calls/pipecat/${voiceCallId}/unmute-ai`)
  },

  getTranscript(voiceCallId: number): Promise<{ lines: TranscriptLine[] }> {
    return apiClient.get(`/api/v1/calls/pipecat/${voiceCallId}/transcript`)
  },

  getSummary(voiceCallId: number): Promise<CallSummary> {
    return apiClient.get(`/api/v1/calls/pipecat/${voiceCallId}/summary`)
  },
}
