/** Period for cost aggregation (matches backend) */
export type CostPeriod = 'today' | 'week' | 'month' | 'quarter';

/** Single LLM call row (maps to backend LLMCall model) */
export interface LLMUsage {
  id: number;
  broker_id: number | null;
  lead_id: number | null;
  provider: string;
  model: string;
  call_type: string;
  used_fallback: number;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
  latency_ms: number | null;
  error: string | null;
  created_at: string;
}

/** Response from GET /api/v1/admin/costs/summary */
export interface CostSummary {
  broker_id: number;
  period: string;
  from: string;
  to: string;
  total_cost_usd: number;
  total_calls: number;
  fallback_calls: number;
  fallback_rate: number;
  avg_latency_ms: number;
  cost_by_provider: Record<string, number>;
  cost_by_call_type: Record<string, number>;
  qualified_leads: number;
  cost_per_qualified_lead_usd: number | null;
  daily_cost_usd: number;
  daily_alert: boolean;
  daily_alert_threshold_usd: number;
}

/** One day in the daily breakdown */
export interface CostDailyPoint {
  date: string;
  cost_usd: number;
}

/** Response from GET /api/v1/admin/costs/daily */
export interface CostDailyResponse {
  broker_id: number;
  period: string;
  daily: CostDailyPoint[];
}

/** One outlier (lead) in outliers response */
export interface CostOutlierItem {
  lead_id: number;
  total_cost_usd: number;
  call_count: number;
  avg_latency_ms: number;
}

/** Response from GET /api/v1/admin/costs/outliers */
export interface CostOutliersResponse {
  broker_id: number;
  period: string;
  outliers: CostOutlierItem[];
}

/** One broker in by-broker response (for future endpoint) */
export interface CostByBrokerItem {
  broker_id: number;
  broker_name?: string;
  total_cost_usd: number;
  total_calls: number;
  leads_qualified?: number;
  cost_per_lead?: number;
}

/** Response from GET /api/v1/admin/costs/by-broker (when implemented) */
export interface CostByBrokerResponse {
  period: string;
  brokers: CostByBrokerItem[];
}

/** Paginated calls response (for future GET /calls) */
export interface CostCallsPage {
  items: LLMUsage[];
  total: number;
  page: number;
  limit: number;
}
