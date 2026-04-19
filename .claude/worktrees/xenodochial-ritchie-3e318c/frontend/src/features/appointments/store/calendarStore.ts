import { create } from 'zustand'
import type {
  CalendarEvent,
  CalendarFilters,
  CalendarViewType,
  CalendarConnection,
} from '../types/calendar.types'

interface PendingSlot {
  start: string
  end: string
}

interface CalendarState {
  events: CalendarEvent[]
  selectedEvent: CalendarEvent | null
  view: CalendarViewType
  filters: CalendarFilters
  isLoading: boolean
  connections: CalendarConnection[]

  // Form modal state
  isFormOpen: boolean
  pendingSlot: PendingSlot | null
  editingAppointmentId: number | null

  // Actions
  setEvents: (events: CalendarEvent[]) => void
  setSelectedEvent: (event: CalendarEvent | null) => void
  setView: (view: CalendarViewType) => void
  setFilter: <K extends keyof CalendarFilters>(key: K, value: CalendarFilters[K]) => void
  resetFilters: () => void
  setLoading: (loading: boolean) => void
  addEvent: (event: CalendarEvent) => void
  updateEvent: (id: string, data: Partial<CalendarEvent>) => void
  removeEvent: (id: string) => void
  setConnections: (connections: CalendarConnection[]) => void

  // Form modal actions
  openCreateForm: (slot?: PendingSlot) => void
  openEditForm: (appointmentId: number) => void
  closeForm: () => void
}

const DEFAULT_FILTERS: CalendarFilters = {
  agentId: undefined,
  status: '',
  provider: '',
  dateStart: undefined,
  dateEnd: undefined,
}

export const useCalendarStore = create<CalendarState>((set) => ({
  events: [],
  selectedEvent: null,
  view: 'timeGridWeek',
  filters: DEFAULT_FILTERS,
  isLoading: false,
  connections: [],

  // Form modal state
  isFormOpen: false,
  pendingSlot: null,
  editingAppointmentId: null,

  setEvents: (events) => set({ events }),
  setSelectedEvent: (selectedEvent) => set({ selectedEvent }),
  setView: (view) => set({ view }),
  setFilter: (key, value) =>
    set((state) => ({ filters: { ...state.filters, [key]: value } })),
  resetFilters: () => set({ filters: DEFAULT_FILTERS }),
  setLoading: (isLoading) => set({ isLoading }),

  addEvent: (event) =>
    set((state) => ({ events: [...state.events, event] })),

  updateEvent: (id, data) =>
    set((state) => ({
      events: state.events.map((e) => (e.id === id ? { ...e, ...data } : e)),
      selectedEvent:
        state.selectedEvent?.id === id
          ? { ...state.selectedEvent, ...data }
          : state.selectedEvent,
    })),

  removeEvent: (id) =>
    set((state) => ({
      events: state.events.filter((e) => e.id !== id),
      selectedEvent: state.selectedEvent?.id === id ? null : state.selectedEvent,
    })),

  setConnections: (connections) => set({ connections }),

  openCreateForm: (slot) =>
    set({ isFormOpen: true, pendingSlot: slot ?? null, editingAppointmentId: null }),

  openEditForm: (appointmentId) =>
    set({ isFormOpen: true, pendingSlot: null, editingAppointmentId: appointmentId }),

  closeForm: () =>
    set({ isFormOpen: false, pendingSlot: null, editingAppointmentId: null }),
}))
