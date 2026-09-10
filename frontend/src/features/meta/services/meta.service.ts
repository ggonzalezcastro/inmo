import { apiClient } from '@/shared/lib/api-client'
import type {
  BrokerUser,
  MetaAsset,
  MetaAssignmentConflict,
  MetaAdCampaign,
  MetaAdCampaignPayload,
  MetaAdsAnalytics,
  MetaAdsPolicy,
  MetaChannel,
  MetaConnection,
  MetaConversationDetail,
  MetaConversationPage,
  MetaHealth,
  MetaMessage,
  MetaMessagePage,
  MetaTaskSuggestion,
  MetaTemplate,
  MetaLeadForm,
  MetaLeadFormPreview,
} from '../types'

export interface MetaConversationFilters {
  cursor?: string
  channel?: string
  asset_id?: number
  assigned_user_id?: number
  pipeline_stage?: string
  project_id?: number
  status?: string
  search?: string
  conflict_only?: boolean
  from_at?: string
  to_at?: string
  limit?: number
}

export const metaService = {
  health: () => apiClient.get<MetaHealth>('/api/v1/meta/health'),
  connections: () => apiClient.get<MetaConnection[]>('/api/v1/meta/connections'),
  assets: () => apiClient.get<MetaAsset[]>('/api/v1/meta/assets'),
  users: () => apiClient.get<{ users: BrokerUser[] }>('/api/broker/users').then((r) => r.users),
  authorize: (channel: MetaChannel) =>
    apiClient.post<{ authorization_url: string }>(`/api/v1/meta/connections/${channel}/authorize`),
  disconnect: (connectionId: number) =>
    apiClient.delete<MetaConnection>(`/api/v1/meta/connections/${connectionId}`),
  revalidate: (connectionId: number) =>
    apiClient.post<MetaConnection>(`/api/v1/meta/connections/${connectionId}/revalidate`),
  sync: (connectionId: number) =>
    apiClient.post<{ ok: boolean; asset_count: number }>(`/api/v1/meta/connections/${connectionId}/sync`),
  updateFeatures: (changes: Partial<Record<string, boolean>>) =>
    apiClient.patch<MetaHealth>('/api/v1/meta/features', changes),
  updateAsset: (assetId: number, changes: Partial<MetaAsset>) =>
    apiClient.patch<MetaAsset>(`/api/v1/meta/assets/${assetId}`, changes),
  templates: (assetId: number) =>
    apiClient.get<MetaTemplate[]>(`/api/v1/meta/assets/${assetId}/message-templates`),

  conversations: (filters: MetaConversationFilters = {}) =>
    apiClient.get<MetaConversationPage>('/api/v1/meta/inbox/conversations', { params: filters }),
  conversation: (conversationId: number) =>
    apiClient.get<MetaConversationDetail>(`/api/v1/meta/inbox/conversations/${conversationId}`),
  messages: (conversationId: number, beforeId?: number) =>
    apiClient.get<MetaMessagePage>(`/api/v1/meta/inbox/conversations/${conversationId}/messages`, {
      params: { before_id: beforeId },
    }),
  read: (conversationId: number) =>
    apiClient.post(`/api/v1/meta/inbox/conversations/${conversationId}/read`),
  send: (
    conversationId: number,
    body: {
      text: string
      generation_mode?: 'manual' | 'ai_draft'
      template_name?: string
      template_language?: string
      template_components?: Array<Record<string, unknown>>
      media_url?: string
      media_type?: 'image' | 'video' | 'audio' | 'document'
    },
  ) => apiClient.post<{ ok: boolean; message: MetaMessage }>(
    `/api/v1/meta/inbox/conversations/${conversationId}/messages`,
    body,
  ),
  summary: (conversationId: number) => apiClient.get<{
    summary: string
    generated_by_ai: boolean
    cached: boolean
    based_on_message_id: number | null
  }>(`/api/v1/meta/inbox/conversations/${conversationId}/ai/summary`),
  draft: (conversationId: number, instruction?: string) => apiClient.post<{
    draft: string
    generated_by_ai: boolean
    generation_mode: 'ai_draft'
    based_on_message_id: number | null
  }>(`/api/v1/meta/inbox/conversations/${conversationId}/ai/draft`, { instruction }),
  suggestTask: (conversationId: number) => apiClient.post<MetaTaskSuggestion>(
    `/api/v1/meta/inbox/conversations/${conversationId}/ai/task-suggestion`,
  ),
  approveTask: (
    conversationId: number,
    body: {
      title: string
      due_at: string
      reminder_minutes_before: number | null
      evidence_message_id: number | null
      assigned_to?: number
    },
  ) => apiClient.post(`/api/v1/meta/inbox/conversations/${conversationId}/ai/task-suggestion/approve`, body),
  conflicts: () => apiClient.get<MetaAssignmentConflict[]>('/api/v1/meta/assignment-conflicts'),
  resolveConflict: (
    conflictId: number,
    resolution: 'keep_current' | 'transfer_to_asset_owner' | 'assign_user' | 'dismiss',
    assignedUserId?: number,
  ) => apiClient.post<MetaAssignmentConflict>(
    `/api/v1/meta/assignment-conflicts/${conflictId}/resolve`,
    { resolution, assigned_user_id: assignedUserId },
  ),

  adsAssets: () => apiClient.get<MetaAsset[]>('/api/v1/meta/ads/catalog/assets'),
  adsProjects: () => apiClient.get<Array<{ id: number; name: string; status: string }>>('/api/v1/meta/ads/catalog/projects'),
  adsPolicy: () => apiClient.get<MetaAdsPolicy>('/api/v1/meta/ads/policy'),
  updateAdsPolicy: (body: MetaAdsPolicy & { expected_version: number }) =>
    apiClient.patch<MetaAdsPolicy>('/api/v1/meta/ads/policy', body),
  adCampaigns: (status?: string) => apiClient.get<MetaAdCampaign[]>('/api/v1/meta/ads/campaigns', { params: { status } }),
  createAdCampaign: (body: MetaAdCampaignPayload) => apiClient.post<MetaAdCampaign>('/api/v1/meta/ads/campaigns', body),
  updateAdCampaign: (id: number, body: MetaAdCampaignPayload & { expected_version: number }) => apiClient.put<MetaAdCampaign>(`/api/v1/meta/ads/campaigns/${id}`, body),
  transitionAdCampaign: (id: number, action: 'submit' | 'approve' | 'reject' | 'publish', expectedVersion: number, comment?: string) =>
    apiClient.post<MetaAdCampaign>(`/api/v1/meta/ads/campaigns/${id}/${action}`, { expected_version: expectedVersion, comment }),
  activateAdCampaign: (id: number, expectedVersion: number) => apiClient.post<MetaAdCampaign>(`/api/v1/meta/ads/campaigns/${id}/activate`, { expected_version: expectedVersion, confirm_spend: true }),
  pauseAdCampaign: (id: number, expectedVersion: number) => apiClient.post<MetaAdCampaign>(`/api/v1/meta/ads/campaigns/${id}/pause`, { expected_version: expectedVersion, confirm_spend: false }),
  leadForms: () => apiClient.get<MetaLeadForm[]>('/api/v1/meta/ads/forms'),
  previewLeadForm: (id: number, body: { project_id: number | null; field_mapping: Record<string, string>; sample_values: Record<string, string> }) =>
    apiClient.post<MetaLeadFormPreview>(`/api/v1/meta/ads/forms/${id}/preview`, body),
  updateLeadForm: (id: number, body: { project_id: number | null; field_mapping: Record<string, string> }) => apiClient.patch<MetaLeadForm>(`/api/v1/meta/ads/forms/${id}`, body),
  syncLeadForms: () => apiClient.post<{ ok: boolean }>('/api/v1/meta/ads/forms/sync'),
  syncAdsInsights: () => apiClient.post<{ ok: boolean }>('/api/v1/meta/ads/insights/sync'),
  adsAnalytics: (params: { date_from: string; date_to: string; account_external_id?: string; campaign_external_id?: string; project_id?: number; executive_id?: number }) => apiClient.get<MetaAdsAnalytics>('/api/v1/meta/ads/analytics', { params }),
  adsAnalyticsLeads: (params: { date_from: string; date_to: string; outcome: 'lead' | 'advised' | 'meeting' | 'reservation' | 'sale'; campaign_external_id?: string; project_id?: number; executive_id?: number; offset?: number; limit?: number }) => apiClient.get<{
    items: Array<{ id: number; name: string | null; phone: string | null; pipeline_stage: string | null; assigned_to: number | null }>
    total: number
    offset: number
    limit: number
  }>('/api/v1/meta/ads/analytics/leads', { params }),
  conversionDiagnostics: () => apiClient.get<Array<{ id: number; event_name: string; status: string; last_error_code: string | null; sent_at: string | null; created_at: string }>>('/api/v1/meta/ads/conversions/diagnostics'),
}
