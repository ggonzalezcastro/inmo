export interface DashboardKPIs {
  active_brokers: number
  total_leads: number
  messages_today: number
  cost_this_month_usd: number
  health_status: 'healthy' | 'degraded' | 'down'
}

export interface SystemHealth {
  status: 'healthy' | 'degraded' | 'down'
  database: string
  redis: string
  circuit_breakers: Record<string, string>
  semantic_cache: {
    hit_rate?: number
    hits?: number
    misses?: number
    [key: string]: unknown
  }
  prompt_cache: {
    active_entries?: number
    [key: string]: unknown
  }
  websocket: {
    total_connections: number
    by_broker: Record<string, number>
    by_broker_named?: Record<string, number>
  }
}
