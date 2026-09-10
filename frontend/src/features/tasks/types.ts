export type TaskStatus = 'open' | 'in_progress' | 'completed'
export type ReminderOffset = 0 | 15 | 60 | 1440 | null
export type AdvisoryChannel =
  | 'whatsapp'
  | 'phone'
  | 'video_call'
  | 'property_visit'
  | 'in_person'
  | 'other'

export interface LeadAdvisory {
  id: number
  lead_id: number
  advisor_id: number | null
  advisor_name: string | null
  recorded_by: number | null
  recorder_name: string | null
  channel: AdvisoryChannel
  occurred_at: string
  notes: string | null
  created_at: string
}

export interface CreateAdvisoryDto {
  advisor_id?: number | null
  channel: AdvisoryChannel
  occurred_at: string
  notes?: string | null
}

export interface LeadNote {
  id: number
  lead_id: number
  body: string
  author_id: number | null
  author_name: string | null
  created_at: string
}

export interface LeadTask {
  id: number
  lead_id: number
  lead_name: string | null
  lead_phone: string | null
  title: string
  status: TaskStatus
  assigned_to: number | null
  assignee_name: string | null
  created_by: number | null
  creator_name: string | null
  completed_by: number | null
  due_at: string
  reminder_minutes_before: ReminderOffset
  reminder_at: string | null
  reminder_sent_at: string | null
  reminder_acknowledged_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface CreateTaskDto {
  title: string
  assigned_to?: number | null
  due_at: string
  reminder_minutes_before: ReminderOffset
}

export interface UpdateTaskDto {
  title?: string
  assigned_to?: number | null
  due_at?: string
  reminder_minutes_before?: ReminderOffset
}

export interface TaskFilters {
  status?: TaskStatus
  assigned_to?: number
  lead_id?: number
  broker_id?: number
  overdue?: boolean
  due_from?: string
  due_to?: string
  skip?: number
  limit?: number
}

export interface AgentOption {
  id: number
  name: string
  email: string
}

export interface PaginatedItems<T> {
  data: T[]
  total: number
  skip: number
  limit: number
}

export interface TaskMetrics {
  total: number
  pending: number
  in_progress: number
  overdue: number
  completed: number
  completion_rate: number
  on_time_rate: number
  avg_resolution_hours: number | null
  avg_delay_hours: number | null
  by_assignee: Array<{
    assigned_to: number | null
    pending: number
    in_progress: number
    overdue: number
    completed: number
  }>
}
