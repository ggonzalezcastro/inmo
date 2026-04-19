import { create } from 'zustand'
import type { Property, PropertyFilters } from '../types'

interface PropertiesState {
  properties: Property[]
  total: number
  isLoading: boolean
  filters: PropertyFilters

  setProperties: (properties: Property[], total: number) => void
  setLoading: (loading: boolean) => void
  setFilter: (key: keyof PropertyFilters, value: unknown) => void
  resetFilters: () => void
  updateProperty: (id: number, data: Partial<Property>) => void
  removeProperty: (id: number) => void
}

const DEFAULT_FILTERS: PropertyFilters = {
  status: '',
  property_type: '',
  commune: '',
  min_price_uf: '',
  max_price_uf: '',
  min_bedrooms: '',
  offset: 0,
  limit: 20,
}

export const usePropertiesStore = create<PropertiesState>((set) => ({
  properties: [],
  total: 0,
  isLoading: false,
  filters: DEFAULT_FILTERS,

  setProperties: (properties, total) => set({ properties, total }),
  setLoading: (isLoading) => set({ isLoading }),
  setFilter: (key, value) =>
    set((state) => ({ filters: { ...state.filters, [key]: value, offset: 0 } })),
  resetFilters: () => set({ filters: DEFAULT_FILTERS }),
  updateProperty: (id, data) =>
    set((state) => ({
      properties: state.properties.map((p) => (p.id === id ? { ...p, ...data } : p)),
    })),
  removeProperty: (id) =>
    set((state) => ({
      properties: state.properties.filter((p) => p.id !== id),
      total: state.total - 1,
    })),
}))
