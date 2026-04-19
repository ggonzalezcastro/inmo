import { create } from 'zustand'
import { dlqApi } from '../services/dlqApi'
import type { DLQEntry } from '../types/dlq.types'
import { toast } from 'sonner'

interface DLQState {
  entries: DLQEntry[]
  total: number
  offset: number
  isLoading: boolean

  fetchEntries: (offset?: number) => Promise<void>
  retryEntry: (id: string) => Promise<void>
  discardEntry: (id: string) => Promise<void>
  bulkRetry: (ids: string[]) => Promise<void>
  bulkDiscard: (ids: string[]) => Promise<void>
}

export const useDLQStore = create<DLQState>((set, get) => ({
  entries: [],
  total: 0,
  offset: 0,
  isLoading: false,

  fetchEntries: async (offset = 0) => {
    set({ isLoading: true })
    try {
      const data = await dlqApi.list(offset)
      set({ entries: data.items, total: data.total, offset, isLoading: false })
    } catch {
      set({ isLoading: false })
      toast.error('Error al cargar tareas fallidas')
    }
  },

  retryEntry: async (id: string) => {
    try {
      await dlqApi.retry(id)
      toast.success('Tarea re-encolada')
      await get().fetchEntries(get().offset)
    } catch {
      toast.error('Error al reintentar tarea')
    }
  },

  discardEntry: async (id: string) => {
    try {
      await dlqApi.discard(id)
      toast.success('Tarea descartada')
      await get().fetchEntries(get().offset)
    } catch {
      toast.error('Error al descartar tarea')
    }
  },

  bulkRetry: async (ids: string[]) => {
    try {
      const res = await dlqApi.bulkRetry(ids)
      const ok = res.results.filter((r) => r.status === 'requeued').length
      toast.success(`${ok} tareas re-encoladas`)
      await get().fetchEntries(get().offset)
    } catch {
      toast.error('Error en bulk retry')
    }
  },

  bulkDiscard: async (ids: string[]) => {
    try {
      const res = await dlqApi.bulkDiscard(ids)
      const ok = res.results.filter((r) => r.status === 'discarded').length
      toast.success(`${ok} tareas descartadas`)
      await get().fetchEntries(get().offset)
    } catch {
      toast.error('Error en bulk discard')
    }
  },
}))
