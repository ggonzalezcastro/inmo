// ──────────────────────────────────────────────
// Overview
// ──────────────────────────────────────────────

export interface MessagesByHourItem {
  hour: string // "2024-01-15T14:00:00"
  inbound: number
  outbound: number
}

export interface AgentDistributionItem {
  agent: string
  count: number
}

export interface PipelineFunnelItem {
  stage: string
  count: number
}

export interface OverviewData {
  period: string
  active_conversations: number
  llm_cost_usd: number
  avg_response_time_ms: number
  escalation_rate_pct: number
  leads_in_human_mode: number
  leads_human_mode_stale: number
  total_tokens: number
  fallback_count: number
  error_count: number
  agent_distribution: AgentDistributionItem[]
  pipeline_funnel: PipelineFunnelItem[]
  messages_by_hour: MessagesByHourItem[]
}

// ──────────────────────────────────────────────
// Conversation Trace
// ──────────────────────────────────────────────

export type TimelineItemType =
  | 'message'
  | 'llm_call'
  | 'handoff'
  | 'error'
  | 'tool'
  | 'pipeline_stage'

export interface TimelineItem {
  id: string
  type: TimelineItemType
  timestamp: string
  // message
  direction?: 'inbound' | 'outbound'
  content?: string
  // llm_call
  provider?: string
  model?: string
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  latency_ms?: number
  cost_usd?: number
  prompt?: string
  completion?: string
  // handoff
  from_agent?: string
  to_agent?: string
  reason?: string
  // error
  error_type?: string
  error_message?: string
  // tool
  tool_name?: string
  tool_input?: Record<string, unknown>
  tool_output?: unknown
  // pipeline_stage
  stage?: string
  previous_stage?: string
}

export interface ConversationSummary {
  lead_id: number
  lead_name: string
  current_stage: string
  current_agent: string
  total_messages: number
  total_tokens: number
  total_cost_usd: number
  last_activity: string
}

export interface ConversationTrace {
  lead_id: number
  summary: ConversationSummary
  timeline: TimelineItem[]
}

// ──────────────────────────────────────────────
// Conversations Search
// ──────────────────────────────────────────────

export interface ConversationSearchItem {
  lead_id: number
  lead_name: string
  current_stage: string
  current_agent: string
  last_message: string
  last_activity: string
  total_messages: number
  human_mode: boolean
}

export interface ConversationSearchResponse {
  items: ConversationSearchItem[]
  total: number
}

// ──────────────────────────────────────────────
// Agent Performance
// ──────────────────────────────────────────────

export interface AgentStats {
  agent_type: string
  messages_handled: number
  p50_latency_ms: number
  p95_latency_ms: number
  avg_tokens: number
  avg_cost_usd: number
  handoffs_out: number
  error_count: number
}

export interface AgentPerformanceData {
  period: string
  agents: AgentStats[]
}

// ──────────────────────────────────────────────
// Handoffs
// ──────────────────────────────────────────────

export interface HandoffFlowItem {
  from_agent: string
  to_agent: string
  count: number
  avg_frustration?: number
}

export interface HandoffFlow {
  period: string
  flows: HandoffFlowItem[]
}

export interface EscalationItem {
  lead_id: number
  lead_name: string
  reason: string
  frustration_score: number
  timestamp: string
  from_agent: string
}

export interface HandoffEscalations {
  period: string
  escalations: EscalationItem[]
}

// ──────────────────────────────────────────────
// Costs
// ──────────────────────────────────────────────

export interface AgentCostItem {
  agent_type: string
  total_cost_usd: number
  total_tokens: number
  call_count: number
  avg_cost_usd: number
}

export interface CostByAgentData {
  period: string
  agents: AgentCostItem[]
}

export interface CostProjection {
  cost_last_7d: number
  daily_avg: number
  monthly_projection: number
  currency: string
}

export interface BrokerCostItem {
  broker_id: number
  broker_name: string | null
  total_cost_usd: number
  total_calls: number
  leads_qualified: number
  cost_per_lead: number | null
}

export interface CostByBrokerData {
  period: string
  brokers: BrokerCostItem[]
}

// ──────────────────────────────────────────────
// Alerts
// ──────────────────────────────────────────────

export type AlertSeverity = 'critical' | 'warning' | 'info'
export type AlertStatus = 'active' | 'acknowledged' | 'resolved' | 'dismissed'

export interface ObservabilityAlert {
  id: string
  alert_type: string
  severity: AlertSeverity
  title: string
  description: string
  status: AlertStatus
  created_at: string
  acknowledged_at?: string
  resolved_at?: string
  broker_id?: number
  lead_id?: number
  metadata?: Record<string, unknown>
}

export interface AlertsResponse {
  alerts: ObservabilityAlert[]
  total: number
}

// ──────────────────────────────────────────────
// Health
// ──────────────────────────────────────────────

export type ComponentStatus = 'ok' | 'degraded' | 'error' | 'unknown'

export interface ComponentHealth {
  name: string
  status: ComponentStatus
  latency_ms?: number
  message?: string
  details?: Record<string, unknown>
}

export interface HealthData {
  status: ComponentStatus
  checked_at: string
  components: ComponentHealth[]
}

// ──────────────────────────────────────────────
// RAG
// ──────────────────────────────────────────────

export interface RAGStrategyStats {
  strategy: string
  search_count: number
  avg_results: number
  avg_latency_ms?: number
}

export interface RAGEffectivenessData {
  period: string
  total_searches: number
  avg_results_per_search: number
  by_strategy: RAGStrategyStats[]
}

// ──────────────────────────────────────────────
// Shared
// ──────────────────────────────────────────────

export type ObservabilityPeriod = '1h' | '24h' | '7d' | '30d'
