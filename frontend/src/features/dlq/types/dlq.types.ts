export interface DLQEntry {
  id: string
  task_name: string
  args: unknown[]
  kwargs: Record<string, unknown>
  exception: string
  traceback?: string
  retries: number
  failed_at: string
}

export interface DLQListResponse {
  total: number
  offset: number
  limit: number
  items: DLQEntry[]
}

export interface BulkResult {
  id: string
  status: 'requeued' | 'discarded' | 'not_found'
}
