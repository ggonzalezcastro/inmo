import { create } from 'zustand'
import type {
  Project,
  ProjectFilters,
  ProjectUnitSummary,
  OrphanUnitsAggregate,
} from '../types'

interface ProjectsState {
  projects: Project[]
  total: number
  orphanUnits: OrphanUnitsAggregate | null
  isLoading: boolean
  filters: ProjectFilters

  // Acordeón
  expandedIds: Set<number>
  /** id `0` = grupo "sin proyecto" */
  unitsByProject: Map<number, ProjectUnitSummary[]>
  loadingUnits: Set<number>

  setProjects: (
    projects: Project[],
    total: number,
    orphanUnits: OrphanUnitsAggregate | null
  ) => void
  setLoading: (loading: boolean) => void
  setFilter: (key: keyof ProjectFilters, value: unknown) => void
  resetFilters: () => void
  updateProject: (id: number, data: Partial<Project>) => void
  removeProject: (id: number) => void

  toggleExpand: (id: number) => void
  setUnits: (projectId: number, units: ProjectUnitSummary[]) => void
  setUnitsLoading: (projectId: number, loading: boolean) => void
  invalidateUnits: (projectId: number) => void
}

const DEFAULT_FILTERS: ProjectFilters = {
  status: '',
  commune: '',
  offset: 0,
  limit: 20,
}

export const useProjectsStore = create<ProjectsState>((set) => ({
  projects: [],
  total: 0,
  orphanUnits: null,
  isLoading: false,
  filters: DEFAULT_FILTERS,
  expandedIds: new Set<number>(),
  unitsByProject: new Map<number, ProjectUnitSummary[]>(),
  loadingUnits: new Set<number>(),

  setProjects: (projects, total, orphanUnits) => set({ projects, total, orphanUnits }),
  setLoading: (isLoading) => set({ isLoading }),
  setFilter: (key, value) =>
    set((state) => ({ filters: { ...state.filters, [key]: value, offset: 0 } })),
  resetFilters: () => set({ filters: DEFAULT_FILTERS }),

  updateProject: (id, data) =>
    set((state) => ({
      projects: state.projects.map((p) => (p.id === id ? { ...p, ...data } : p)),
    })),
  removeProject: (id) =>
    set((state) => ({
      projects: state.projects.filter((p) => p.id !== id),
      total: state.total - 1,
    })),

  toggleExpand: (id) =>
    set((state) => {
      const next = new Set(state.expandedIds)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return { expandedIds: next }
    }),
  setUnits: (projectId, units) =>
    set((state) => {
      const next = new Map(state.unitsByProject)
      next.set(projectId, units)
      return { unitsByProject: next }
    }),
  setUnitsLoading: (projectId, loading) =>
    set((state) => {
      const next = new Set(state.loadingUnits)
      if (loading) next.add(projectId)
      else next.delete(projectId)
      return { loadingUnits: next }
    }),
  invalidateUnits: (projectId) =>
    set((state) => {
      const next = new Map(state.unitsByProject)
      next.delete(projectId)
      return { unitsByProject: next }
    }),
}))
