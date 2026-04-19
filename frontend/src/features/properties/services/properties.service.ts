import { apiClient } from '@/shared/lib/api-client'
import type { PaginatedResponse } from '@/shared/types/api'
import type { Property, PropertyFilters, CreatePropertyDto, UpdatePropertyDto } from '../types'

interface ListPropertiesResponse {
  total: number
  offset: number
  limit: number
  items: Property[]
}

export const propertiesService = {
  async getProperties(filters: Partial<PropertyFilters> = {}): Promise<PaginatedResponse<Property>> {
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v !== '' && v !== undefined && v !== null)
    )
    const res: ListPropertiesResponse = await apiClient.get('/api/v1/properties', { params })
    return { data: res.items, total: res.total, skip: res.offset, limit: res.limit }
  },

  async getProperty(id: number): Promise<Property> {
    return apiClient.get(`/api/v1/properties/${id}`)
  },

  async createProperty(data: CreatePropertyDto, brokerIdOverride?: number): Promise<Property> {
    const params = brokerIdOverride ? { broker_id: brokerIdOverride } : {}
    return apiClient.post('/api/v1/properties', data, { params })
  },

  async updateProperty(id: number, data: UpdatePropertyDto, brokerIdOverride?: number): Promise<Property> {
    const params = brokerIdOverride ? { broker_id: brokerIdOverride } : {}
    return apiClient.put(`/api/v1/properties/${id}`, data, { params })
  },

  async deleteProperty(id: number): Promise<void> {
    return apiClient.delete(`/api/v1/properties/${id}`)
  },

  async getMigrationStatus(brokerIdOverride?: number): Promise<{
    total_kb_property_entries: number
    migrated_count: number
    unmigrated_count: number
  }> {
    const params = brokerIdOverride ? { broker_id: brokerIdOverride } : {}
    return apiClient.get('/api/v1/properties/migration-status', { params })
  },

  async importFromKb(options: { brokerIdOverride?: number; dryRun?: boolean } = {}): Promise<{
    dry_run: boolean
    total_kb_entries: number
    migrated: number
    skipped_already_exists: number
    errors: number
    preview?: Array<{ kb_entry_id: number; name: string; commune: string | null; price_uf: number | null }>
  }> {
    const params: Record<string, unknown> = {}
    if (options.brokerIdOverride) params.broker_id = options.brokerIdOverride
    if (options.dryRun) params.dry_run = true
    return apiClient.post('/api/v1/properties/import-from-kb', {}, { params })
  },

  async generateSampleProperties(
    brokerIdOverride?: number,
    count = 10,
    projectCount = 0,
  ): Promise<{
    created: number
    ids: number[]
    embed_failures: number
  }> {
    const params: Record<string, unknown> = { count }
    if (projectCount > 0) params.project_count = projectCount
    if (brokerIdOverride) params.broker_id = brokerIdOverride
    return apiClient.post('/api/v1/properties/generate-sample', {}, { params })
  },
}
