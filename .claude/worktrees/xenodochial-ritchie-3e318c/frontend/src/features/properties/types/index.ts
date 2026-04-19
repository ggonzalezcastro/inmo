export type PropertyStatus = 'available' | 'reserved' | 'sold' | 'rented' | 'archived'
export type PropertyType = 'departamento' | 'casa' | 'terreno' | 'oficina'

export interface PropertyImage {
  url: string
  caption?: string
  order?: number
}

export interface NearbyPlace {
  type: string
  name: string
  distance_m?: number
}

export interface Property {
  id: number
  broker_id: number
  name: string | null
  internal_code: string | null
  property_type: PropertyType | null
  status: PropertyStatus
  commune: string | null
  city: string | null
  region: string | null
  address: string | null
  latitude: number | null
  longitude: number | null
  price_uf: number | null
  price_clp: number | null
  bedrooms: number | null
  bathrooms: number | null
  parking_spots: number | null
  storage_units: number | null
  square_meters_total: number | null
  square_meters_useful: number | null
  floor_number: number | null
  total_floors: number | null
  orientation: string | null
  year_built: number | null
  description: string | null
  highlights: string | null
  amenities: string[] | null
  nearby_places: NearbyPlace[] | null
  images: PropertyImage[] | null
  financing_options: string[] | null
  floor_plan_url: string | null
  virtual_tour_url: string | null
  common_expenses_clp: number | null
  subsidio_eligible: boolean
  published_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface CreatePropertyDto {
  name?: string
  internal_code?: string
  property_type?: PropertyType
  status?: PropertyStatus
  commune?: string
  city?: string
  region?: string
  address?: string
  latitude?: number
  longitude?: number
  price_uf?: number
  price_clp?: number
  bedrooms?: number
  bathrooms?: number
  parking_spots?: number
  storage_units?: number
  square_meters_total?: number
  square_meters_useful?: number
  floor_number?: number
  total_floors?: number
  orientation?: string
  year_built?: number
  description?: string
  highlights?: string
  amenities?: string[]
  nearby_places?: NearbyPlace[]
  images?: PropertyImage[]
  financing_options?: string[]
  floor_plan_url?: string
  virtual_tour_url?: string
  common_expenses_clp?: number
  subsidio_eligible?: boolean
}

export type UpdatePropertyDto = CreatePropertyDto

export interface PropertyFilters {
  status?: PropertyStatus | ''
  property_type?: PropertyType | ''
  commune?: string
  min_price_uf?: number | ''
  max_price_uf?: number | ''
  min_bedrooms?: number | ''
  broker_id?: number | null
  offset?: number
  limit?: number
}
