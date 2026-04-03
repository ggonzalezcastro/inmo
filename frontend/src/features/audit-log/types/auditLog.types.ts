export interface AuditLogEntry {
  id: number
  user_id: number | null
  user_email: string | null
  broker_id: number | null
  action: string
  resource_type: string
  resource_id: number
  changes: Record<string, unknown> | null
  ip_address: string | null
  timestamp: string
}

export interface AuditLogResponse {
  total: number
  page: number
  limit: number
  items: AuditLogEntry[]
}

export interface AuditLogFilters {
  action?: string
  resource_type?: string
  broker_id?: number
  from_date?: string
  to_date?: string
  page: number
}
