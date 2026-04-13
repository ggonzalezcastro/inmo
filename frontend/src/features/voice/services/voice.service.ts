import { apiClient } from '@/shared/lib/api-client'
import type {
  CallStartRequest,
  CallStartResponse,
  AgentVoiceProfile,
  AgentVoiceTemplate,
  VapiVoice,
  VoiceEntry,
} from '../types'

export const voiceService = {
  // ── Call lifecycle ──────────────────────────────────────────────────────────

  startCall(data: CallStartRequest): Promise<CallStartResponse> {
    return apiClient.post('/api/v1/calls/start', data)
  },

  endCall(voiceCallId: number): Promise<{ ok: boolean }> {
    return apiClient.post(`/api/v1/calls/${voiceCallId}/end`)
  },

  /**
   * Link the VAPI-assigned call ID to our VoiceCall row.
   * Must be called immediately after the @vapi-ai/web SDK fires 'call-start'.
   */
  linkExternalId(voiceCallId: number, externalCallId: string): Promise<{ ok: boolean }> {
    return apiClient.patch(`/api/v1/calls/${voiceCallId}/external-id`, {
      external_call_id: externalCallId,
    })
  },

  getCallStatus(voiceCallId: number): Promise<{ status: string; call_output: Record<string, unknown> | null }> {
    return apiClient.get(`/api/v1/calls/${voiceCallId}/status`)
  },

  // ── Agent voice profile ─────────────────────────────────────────────────────

  getMyProfile(): Promise<AgentVoiceProfile> {
    return apiClient.get('/api/v1/calls/agents/me/voice-profile')
  },

  updateMyProfile(data: Partial<AgentVoiceProfile>): Promise<AgentVoiceProfile> {
    return apiClient.put('/api/v1/calls/agents/me/voice-profile', data)
  },

  // ── Broker templates (admin) ─────────────────────────────────────────────────

  listTemplates(): Promise<AgentVoiceTemplate[]> {
    return apiClient.get('/api/v1/calls/brokers/voice-templates')
  },

  createTemplate(data: Partial<AgentVoiceTemplate>): Promise<AgentVoiceTemplate> {
    return apiClient.post('/api/v1/calls/brokers/voice-templates', data)
  },

  updateTemplate(id: number, data: Partial<AgentVoiceTemplate>): Promise<AgentVoiceTemplate> {
    return apiClient.put(`/api/v1/calls/brokers/voice-templates/${id}`, data)
  },

  deleteTemplate(id: number): Promise<void> {
    return apiClient.delete(`/api/v1/calls/brokers/voice-templates/${id}`)
  },

  getAvailableVoices(templateId: number): Promise<{ voice_ids: (string | VoiceEntry)[] }> {
    return apiClient.get(`/api/v1/calls/brokers/voice-templates/${templateId}/available-voices`)
  },

  getAvailableTones(templateId: number): Promise<{ tones: string[] }> {
    return apiClient.get(`/api/v1/calls/brokers/voice-templates/${templateId}/available-tones`)
  },

  assignTemplate(userId: number, templateId: number): Promise<AgentVoiceProfile> {
    return apiClient.put(`/api/v1/calls/brokers/agents/${userId}/voice-template`, { template_id: templateId })
  },

  // ── VAPI voice catalog ───────────────────────────────────────────────────────

  getVoiceCatalog(): Promise<{ voices: VapiVoice[] }> {
    return apiClient.get('/api/v1/calls/brokers/voice-catalog')
  },
}
