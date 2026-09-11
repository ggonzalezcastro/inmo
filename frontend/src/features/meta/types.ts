export type MetaChannel = 'whatsapp' | 'instagram' | 'messenger' | 'business'
export type ConversationChannel = 'whatsapp' | 'instagram' | 'facebook'

export interface MetaHealth {
  configured: boolean
  global_enabled: boolean
  broker_enabled: boolean
  graph_api_version: string
  channels: Record<'whatsapp' | 'instagram' | 'messenger' | 'ads' | 'lead_ads' | 'conversions_api', boolean>
  overrides: Record<string, boolean>
  configuration: {
    app_credentials: boolean
    webhook_verify_token: boolean
    oauth_redirect_configured: boolean
    oauth_redirect_https: boolean
    embedded_signup_config: boolean
    credential_encryption_key: boolean
  }
  legacy_whatsapp_fallback_enabled: boolean
}

export interface MetaConnection {
  id: number
  broker_id: number
  owner_type: 'broker' | 'user'
  owner_user_id: number | null
  connected_by_user_id: number | null
  auth_mode: string
  external_principal_id: string
  display_name: string | null
  scopes: string[]
  status: string
  expires_at: string | null
  last_validated_at: string | null
  revoked_at: string | null
  disconnected_at: string | null
  last_error_code: string | null
  created_at: string
  updated_at: string
}

export interface MetaAsset {
  id: number
  broker_id: number
  connection_id: number
  asset_type: string
  channel: string | null
  external_id: string
  parent_external_id: string | null
  display_name: string | null
  owner_type: 'broker' | 'user'
  owner_user_id: number | null
  assigned_user_id: number | null
  capabilities: string[]
  approval_status: 'pending_approval' | 'approved' | 'rejected'
  status: 'active' | 'paused' | 'disabled' | 'error'
  is_default: boolean
  ai_mode: 'suggestion' | 'supervised_auto' | 'human'
  last_synced_at: string | null
  last_error_code: string | null
  created_at: string
  updated_at: string
}

export interface MetaTemplate {
  id: number
  waba_external_id: string
  external_id: string
  name: string
  language: string
  category: string | null
  status: string
  components: Array<Record<string, unknown>>
  last_synced_at: string | null
}

export interface BrokerUser {
  id: number
  name: string
  email: string
  role: string
  broker_id: number | null
  is_active: boolean
}

export interface MetaInboxAsset {
  id: number
  type: string
  channel: string | null
  name: string | null
  owner_type: string
  owner_user_id: number | null
  assigned_user_id: number | null
  status: string
  approval_status: string
  ai_mode: string
}

export interface MetaInboxLead {
  id: number
  name: string | null
  phone: string | null
  email: string | null
  pipeline_stage: string | null
  status: string | null
  assigned_to: number | null
  assigned_agent_name: string | null
}

export interface MetaConversation {
  id: number
  channel: ConversationChannel
  status: string
  last_message: string | null
  last_message_at: string | null
  last_message_direction: 'in' | 'out' | null
  unread_count: number
  messaging_window_expires_at: string | null
  assignment_conflict: boolean
  human_mode: boolean
  message_count: number
  asset: MetaInboxAsset | null
  lead: MetaInboxLead
}

export interface MetaConversationPage {
  items: MetaConversation[]
  next_cursor: string | null
  has_more: boolean
}

export interface MetaMessage {
  id: number
  provider: string
  message_text: string
  direction: 'in' | 'out'
  status: 'pending' | 'sent' | 'delivered' | 'read' | 'failed'
  message_type: string
  generation_mode: string
  channel_message_id: string | null
  reply_to_external_id: string | null
  sent_by_user_id: number | null
  attachments: Array<Record<string, unknown>> | null
  remote_error_code: string | null
  remote_error_subcode: string | null
  created_at: string
}

export interface MetaMessagePage {
  items: MetaMessage[]
  next_before_id: number | null
  has_more: boolean
}

export interface MetaConversationDetail {
  conversation: MetaConversation
  messages: MetaMessagePage
}

export interface MetaTaskSuggestion {
  suggested: boolean
  title: string | null
  due_at: string | null
  reminder_minutes_before: number | null
  evidence_message_id: number | null
  evidence: string | null
  needs_review: boolean
  reason: string | null
  generated_by_ai: boolean
}

export interface MetaAssignmentConflict {
  id: number
  broker_id: number
  lead_id: number
  asset_id: number
  current_assignee_id: number | null
  asset_owner_id: number | null
  status: string
  resolution: string | null
  resolved_by_user_id: number | null
  resolved_at: string | null
  created_at: string
}

export type MetaAdCampaignStatus =
  | 'draft' | 'pending_review' | 'rejected' | 'approved' | 'publishing'
  | 'published_paused' | 'active' | 'paused' | 'completed' | 'partial_error'

export interface MetaAdsPolicy {
  currency: 'CLP' | 'USD'
  max_daily_budget: number
  max_lifetime_budget: number
  require_budget_increase_confirmation: boolean
  version: number
}

export interface MetaAdSet {
  id: number
  name: string
  optimization_goal: string
  billing_event: string
  targeting: Record<string, unknown>
  promoted_object: Record<string, unknown>
  start_at: string | null
  end_at: string | null
  external_id: string | null
  remote_status: string | null
}

export interface MetaAdCreative {
  id: number
  page_asset_id: number
  instagram_asset_id: number | null
  name: string
  primary_text: string
  headline: string
  description: string | null
  call_to_action: string
  destination_url: string | null
  media_url: string | null
  media_hash: string | null
  external_id: string | null
  validation_result: Record<string, unknown>
}

export interface MetaAdCampaign {
  id: number
  broker_id: number
  ad_account_asset_id: number
  project_id: number | null
  created_by_user_id: number | null
  approved_by_user_id: number | null
  operation_uuid: string
  name: string
  objective: string
  destination_type: string
  special_ad_category: 'HOUSING'
  status: MetaAdCampaignStatus
  daily_budget: number | null
  lifetime_budget: number | null
  currency: string
  version: number
  external_id: string | null
  remote_status: string | null
  submission_snapshot: Record<string, unknown> | null
  rejection_comment: string | null
  last_error_code: string | null
  last_error_detail: string | null
  submitted_at: string | null
  approved_at: string | null
  published_at: string | null
  activated_at: string | null
  paused_at: string | null
  created_at: string
  updated_at: string
  ad_sets: MetaAdSet[]
  creatives: MetaAdCreative[]
  ads: Array<{ id: number; name: string; external_id: string | null; remote_status: string | null }>
}

export interface MetaAdCampaignPayload {
  name: string
  ad_account_asset_id: number
  project_id?: number
  objective: 'OUTCOME_LEADS' | 'OUTCOME_TRAFFIC' | 'OUTCOME_ENGAGEMENT'
  destination_type: 'lead_form' | 'whatsapp' | 'instagram' | 'website'
  special_ad_category: 'HOUSING'
  daily_budget?: number
  lifetime_budget?: number
  currency: 'CLP' | 'USD'
  ad_set: {
    name: string
    optimization_goal: string
    billing_event: string
    targeting: Record<string, unknown>
    promoted_object: Record<string, unknown>
    start_at?: string
    end_at?: string
  }
  creative: {
    page_asset_id: number
    instagram_asset_id?: number
    name: string
    primary_text: string
    headline: string
    description?: string
    call_to_action: string
    destination_url?: string
    media_url?: string
  }
}

export interface MetaLeadForm {
  id: number
  page_asset_id: number
  project_id: number | null
  external_id: string
  name: string
  status: string
  questions: Array<Record<string, unknown>>
  field_mapping: Record<string, string>
  last_synced_at: string | null
}

export interface MetaLeadFormPreview {
  lead_payload: {
    phone: string | null
    name: string | null
    email: string | null
    tags: string[]
    metadata: Record<string, unknown>
  }
  source_values: Record<string, string>
  warnings: string[]
}

export interface MetaAdsAnalytics {
  kpis: {
    spend: number
    impressions: number
    reach: number
    clicks: number
    conversations: number
    meta_leads: number
    crm_leads: number
    advised: number
    meetings: number
    reservations: number
    sales: number
    sales_uf: number
    sales_clp: number
    cost_per_conversation: number | null
    cost_per_lead: number | null
    cost_per_advised: number | null
    cost_per_meeting: number | null
    cost_per_reservation: number | null
    cost_per_sale: number | null
  }
  trend: Array<{ date: string; spend: number; leads: number; conversations: number }>
  campaigns: Array<{ campaign_external_id: string; spend: number; impressions: number; clicks: number; leads: number }>
  freshness_at: string | null
  partial_sync: boolean
}
