import { apiClient } from '@/shared/lib/api-client'
import type {
  AgentOption,
  CreateAdvisoryDto,
  CreateTaskDto,
  LeadNote,
  LeadAdvisory,
  LeadTask,
  PaginatedItems,
  TaskFilters,
  TaskMetrics,
  UpdateTaskDto,
} from '../types'

function cleanParams(values: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(values).filter(([, value]) => value !== undefined && value !== null && value !== '')
  )
}

export const tasksService = {
  getAdvisories(leadId: number, skip = 0, limit = 50): Promise<PaginatedItems<LeadAdvisory>> {
    return apiClient.get(`/api/v1/leads/${leadId}/advisories`, { params: { skip, limit } })
  },

  createAdvisory(leadId: number, payload: CreateAdvisoryDto): Promise<LeadAdvisory> {
    return apiClient.post(`/api/v1/leads/${leadId}/advisories`, payload)
  },

  getNotes(leadId: number, skip = 0, limit = 50): Promise<PaginatedItems<LeadNote>> {
    return apiClient.get(`/api/v1/leads/${leadId}/notes`, { params: { skip, limit } })
  },

  createNote(leadId: number, body: string): Promise<LeadNote> {
    return apiClient.post(`/api/v1/leads/${leadId}/notes`, { body })
  },

  getLeadTasks(leadId: number): Promise<PaginatedItems<LeadTask>> {
    return apiClient.get(`/api/v1/leads/${leadId}/tasks`, { params: { limit: 200 } })
  },

  getTasks(filters: TaskFilters = {}): Promise<PaginatedItems<LeadTask>> {
    return apiClient.get('/api/v1/tasks', { params: cleanParams(filters as Record<string, unknown>) })
  },

  getTask(taskId: number): Promise<LeadTask> {
    return apiClient.get(`/api/v1/tasks/${taskId}`)
  },

  getMetrics(assignedTo?: number): Promise<TaskMetrics> {
    return apiClient.get('/api/v1/tasks/metrics/summary', {
      params: assignedTo ? { assigned_to: assignedTo } : undefined,
    })
  },

  getPendingReminders(): Promise<LeadTask[]> {
    return apiClient.get('/api/v1/tasks/reminders/pending', { params: { limit: 100 } })
  },

  acknowledgeReminder(taskId: number): Promise<void> {
    return apiClient.post(`/api/v1/tasks/${taskId}/reminder/ack`)
  },

  createTask(leadId: number, payload: CreateTaskDto): Promise<LeadTask> {
    return apiClient.post(`/api/v1/leads/${leadId}/tasks`, payload)
  },

  updateTask(taskId: number, payload: UpdateTaskDto): Promise<LeadTask> {
    return apiClient.patch(`/api/v1/tasks/${taskId}`, payload)
  },

  completeTask(taskId: number): Promise<LeadTask> {
    return apiClient.post(`/api/v1/tasks/${taskId}/complete`)
  },

  startTask(taskId: number): Promise<LeadTask> {
    return apiClient.post(`/api/v1/tasks/${taskId}/start`)
  },

  reopenTask(taskId: number): Promise<LeadTask> {
    return apiClient.post(`/api/v1/tasks/${taskId}/reopen`)
  },

  deleteTask(taskId: number): Promise<void> {
    return apiClient.delete(`/api/v1/tasks/${taskId}`)
  },

  listAgents(): Promise<AgentOption[]> {
    return apiClient.get('/api/v1/agents/')
  },
}
