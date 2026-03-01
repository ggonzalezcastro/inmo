import { create } from 'zustand'
import type { Lead, LeadFilters } from '../types'

interface LeadsState {
  leads: Lead[]
  total: number
  isLoading: boolean
  filters: LeadFilters

  setLeads: (leads: Lead[], total: number) => void
  setLoading: (loading: boolean) => void
  setFilter: (key: keyof LeadFilters, value: unknown) => void
  resetFilters: () => void
  updateLead: (id: number, data: Partial<Lead>) => void
  removeLead: (id: number) => void
}

const DEFAULT_FILTERS: LeadFilters = {
  search: '',
  status: '',
  pipeline_stage: '',
  skip: 0,
  limit: 20,
}

export const useLeadsStore = create<LeadsState>((set) => ({
  leads: [],
  total: 0,
  isLoading: false,
  filters: DEFAULT_FILTERS,

  setLeads: (leads, total) => set({ leads, total }),
  setLoading: (isLoading) => set({ isLoading }),
  setFilter: (key, value) =>
    set((state) => ({ filters: { ...state.filters, [key]: value, skip: 0 } })),
  resetFilters: () => set({ filters: DEFAULT_FILTERS }),
  updateLead: (id, data) =>
    set((state) => ({
      leads: state.leads.map((l) => (l.id === id ? { ...l, ...data } : l)),
    })),
  removeLead: (id) =>
    set((state) => ({ leads: state.leads.filter((l) => l.id !== id), total: state.total - 1 })),
}))
