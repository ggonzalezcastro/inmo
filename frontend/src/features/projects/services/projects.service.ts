import { apiClient } from '@/shared/lib/api-client'
import type {
  Project,
  ProjectFilters,
  CreateProjectDto,
  UpdateProjectDto,
  OrphanUnitsAggregate,
  ProjectUnitSummary,
} from '../types'

interface ListProjectsResponse {
  total: number
  offset: number
  limit: number
  items: Project[]
  orphan_units: OrphanUnitsAggregate | null
}

interface ListProjectUnitsResponse {
  total: number
  offset: number
  limit: number
  items: ProjectUnitSummary[]
}

export const projectsService = {
  async getProjects(filters: Partial<ProjectFilters> = {}): Promise<ListProjectsResponse> {
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v !== '' && v !== undefined && v !== null)
    )
    return apiClient.get('/api/v1/projects', { params })
  },

  async getProject(id: number, brokerIdOverride?: number): Promise<Project> {
    const params = brokerIdOverride ? { broker_id: brokerIdOverride } : {}
    return apiClient.get(`/api/v1/projects/${id}`, { params })
  },

  async createProject(data: CreateProjectDto, brokerIdOverride?: number): Promise<Project> {
    const params = brokerIdOverride ? { broker_id: brokerIdOverride } : {}
    return apiClient.post('/api/v1/projects', data, { params })
  },

  async updateProject(id: number, data: UpdateProjectDto, brokerIdOverride?: number): Promise<Project> {
    const params = brokerIdOverride ? { broker_id: brokerIdOverride } : {}
    return apiClient.put(`/api/v1/projects/${id}`, data, { params })
  },

  async deleteProject(id: number, brokerIdOverride?: number): Promise<void> {
    const params = brokerIdOverride ? { broker_id: brokerIdOverride } : {}
    return apiClient.delete(`/api/v1/projects/${id}`, { params })
  },

  async getProjectUnits(
    id: number,
    options: {
      status?: string
      tipologia?: string
      offset?: number
      limit?: number
      brokerIdOverride?: number
    } = {}
  ): Promise<ListProjectUnitsResponse> {
    const params: Record<string, unknown> = {}
    if (options.status) params.status = options.status
    if (options.tipologia) params.tipologia = options.tipologia
    if (options.offset != null) params.offset = options.offset
    if (options.limit != null) params.limit = options.limit
    if (options.brokerIdOverride) params.broker_id = options.brokerIdOverride
    return apiClient.get(`/api/v1/projects/${id}/properties`, { params })
  },
}
