import { create } from 'zustand'
import { superAdminApi } from '../services/superAdminApi'
import type { DashboardKPIs, SystemHealth } from '../types/superAdmin.types'

interface SuperAdminState {
  kpis: DashboardKPIs | null
  health: SystemHealth | null
  isLoadingKPIs: boolean
  isLoadingHealth: boolean
  error: string | null

  fetchKPIs: () => Promise<void>
  fetchHealth: () => Promise<void>
}

export const useSuperAdminStore = create<SuperAdminState>((set) => ({
  kpis: null,
  health: null,
  isLoadingKPIs: false,
  isLoadingHealth: false,
  error: null,

  fetchKPIs: async () => {
    set({ isLoadingKPIs: true, error: null })
    try {
      const data = await superAdminApi.getDashboard()
      set({ kpis: data, isLoadingKPIs: false })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al cargar KPIs'
      set({ error: msg, isLoadingKPIs: false })
    }
  },

  fetchHealth: async () => {
    set({ isLoadingHealth: true, error: null })
    try {
      const data = await superAdminApi.getHealth()
      set({ health: data, isLoadingHealth: false })
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al cargar health'
      set({ error: msg, isLoadingHealth: false })
    }
  },
}))
