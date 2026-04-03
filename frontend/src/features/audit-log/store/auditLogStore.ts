import { create } from 'zustand'
import { auditLogApi } from '../services/auditLogApi'
import type { AuditLogEntry, AuditLogFilters } from '../types/auditLog.types'
import { toast } from 'sonner'

interface AuditLogState {
  entries: AuditLogEntry[]
  total: number
  isLoading: boolean
  filters: AuditLogFilters

  setFilters: (filters: Partial<AuditLogFilters>) => void
  fetchEntries: () => Promise<void>
}

export const useAuditLogStore = create<AuditLogState>((set, get) => ({
  entries: [],
  total: 0,
  isLoading: false,
  filters: { page: 1 },

  setFilters: (partial) => {
    set((s) => ({ filters: { ...s.filters, ...partial, page: 1 } }))
    get().fetchEntries()
  },

  fetchEntries: async () => {
    set({ isLoading: true })
    try {
      const data = await auditLogApi.list(get().filters)
      set({ entries: data.items, total: data.total, isLoading: false })
    } catch {
      set({ isLoading: false })
      toast.error('Error al cargar audit log')
    }
  },
}))
