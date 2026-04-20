export type ProjectStatus =
  | 'en_blanco'
  | 'en_construccion'
  | 'en_venta'
  | 'entrega_inmediata'
  | 'terminado'
  | 'agotado'

export interface ProjectImage {
  url: string
  caption?: string
  order?: number
}

export interface Project {
  id: number
  broker_id: number
  name: string
  code: string | null
  description: string | null
  developer: string | null
  status: ProjectStatus
  commune: string | null
  city: string | null
  region: string | null
  address: string | null
  latitude: number | null
  longitude: number | null
  delivery_date: string | null
  total_units: number | null
  available_units: number | null
  common_amenities: string[] | null
  images: ProjectImage[] | null
  brochure_url: string | null
  virtual_tour_url: string | null
  subsidio_eligible: boolean
  financing_options: string[] | null
  highlights: string | null
  created_at: string | null
  updated_at: string | null
  // Aggregates desde el backend
  units_count?: number
  units_available?: number
  units_reserved?: number
  units_sold?: number
  min_price_uf?: number | null
  max_price_uf?: number | null
}

export interface OrphanUnitsAggregate {
  units_count: number
  units_available: number
  units_reserved: number
  units_sold: number
  min_price_uf: number | null
  max_price_uf: number | null
}

export interface CreateProjectDto {
  name: string
  code?: string
  description?: string
  developer?: string
  status?: ProjectStatus
  commune?: string
  city?: string
  region?: string
  address?: string
  latitude?: number
  longitude?: number
  delivery_date?: string
  total_units?: number
  available_units?: number
  common_amenities?: string[]
  images?: ProjectImage[]
  brochure_url?: string
  virtual_tour_url?: string
  subsidio_eligible?: boolean
  financing_options?: string[]
  highlights?: string
}

export type UpdateProjectDto = Partial<CreateProjectDto>

export interface ProjectFilters {
  // Project-level
  status?: ProjectStatus | ''
  commune?: string
  name?: string
  developer?: string
  // Unit-level (project must have ≥1 matching unit)
  unit_status?: string
  property_type?: string
  bedrooms?: number | ''
  bathrooms?: number | ''
  min_price_uf?: number | ''
  max_price_uf?: number | ''
  min_sqm?: number | ''
  max_sqm?: number | ''
  orientation?: string
  min_floor?: number | ''
  max_floor?: number | ''
  // Pagination / tenant
  broker_id?: number | null
  offset?: number
  limit?: number
}

export interface ProjectUnitSummary {
  id: number
  codigo: string | null
  tipologia: string | null
  name: string | null
  property_type: string | null
  status: string
  bedrooms: number | null
  bathrooms: number | null
  square_meters_useful: number | null
  price_uf: number | null
  has_offer: boolean
  offer_price_uf: number | null
  floor_number: number | null
  orientation: string | null
}
