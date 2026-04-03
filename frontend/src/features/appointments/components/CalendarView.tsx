import { useEffect, useRef, useCallback, useState } from 'react'
import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import listPlugin from '@fullcalendar/list'
import interactionPlugin from '@fullcalendar/interaction'
import type { EventResizeDoneArg } from '@fullcalendar/interaction'
import type {
  EventClickArg,
  EventContentArg,
  EventDropArg,
  DateSelectArg,
} from '@fullcalendar/core'
import { Settings } from 'lucide-react'
import { toast } from 'sonner'
import { useCalendarStore } from '../store/calendarStore'
import { calendarService } from '../services/calendar.service'
import { calendarProvidersService } from '../services/calendarProviders.service'
import { CalendarToolbar } from './CalendarToolbar'
import { CalendarEventChip } from './CalendarEventChip'
import { CalendarConnectionPanel } from './CalendarConnectionPanel'
import { AppointmentDetailModal } from './AppointmentDetailModal'
import { AppointmentFormModal } from './AppointmentFormModal'
import { useAuthStore } from '@/features/auth/store/authStore'
import { apiClient } from '@/shared/lib/api-client'
import { getErrorMessage } from '@/shared/types/api'
import type { CalendarViewType } from '../types/calendar.types'

interface Agent {
  id: number
  name: string
  email: string
}

export function CalendarView() {
  const calendarRef = useRef<FullCalendar>(null)
  const [showConnectionPanel, setShowConnectionPanel] = useState(false)
  const [agents, setAgents] = useState<Agent[]>([])

  const {
    events,
    view,
    filters,
    isLoading,
    connections,
    setEvents,
    setView,
    setFilter,
    setLoading,
    setSelectedEvent,
    setConnections,
    updateEvent,
    removeEvent,
    openCreateForm,
  } = useCalendarStore()

  const { user, isAdmin, isSuperAdmin } = useAuthStore()
  const canSeeAllAgents = isAdmin() || isSuperAdmin()

  // ── Load calendar connections on mount ─────────────────────────────────────

  useEffect(() => {
    calendarProvidersService.getStatus()
      .then(setConnections)
      .catch(() => {/* silently fail — non-critical */})
  }, [setConnections])

  // ── Load agents list for admin filter ─────────────────────────────────────

  useEffect(() => {
    if (!canSeeAllAgents) return
    apiClient.get<Agent[]>('/api/v1/agents/')
      .then(setAgents)
      .catch(() => {/* non-critical */})
  }, [canSeeAllAgents])

  // ── Set default view for mobile ────────────────────────────────────────────

  useEffect(() => {
    if (window.innerWidth < 768 && view === 'timeGridWeek') {
      setView('listWeek')
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Fetch events ───────────────────────────────────────────────────────────

  const fetchEvents = useCallback(async () => {
    setLoading(true)
    try {
      const appliedFilters = { ...filters }
      // Agents always see only their own appointments
      if (user && !canSeeAllAgents) {
        appliedFilters.agentId = user.id
      }
      const data = await calendarService.fetchEvents(appliedFilters)
      setEvents(data)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [filters, user, canSeeAllAgents, setEvents, setLoading])

  useEffect(() => {
    void fetchEvents()
  }, [fetchEvents])

  // ── Sync FullCalendar internal view when store view changes ────────────────

  useEffect(() => {
    calendarRef.current?.getApi().changeView(view)
  }, [view])

  // ── Toolbar callbacks ──────────────────────────────────────────────────────

  const handlePrev = () => calendarRef.current?.getApi().prev()
  const handleNext = () => calendarRef.current?.getApi().next()
  const handleToday = () => calendarRef.current?.getApi().today()

  const handleViewChange = (newView: CalendarViewType) => {
    setView(newView)
    calendarRef.current?.getApi().changeView(newView)
  }

  const getTitle = () => calendarRef.current?.getApi().view.title ?? ''

  const handleAgentChange = (agentId: number | undefined) => {
    setFilter('agentId', agentId)
  }

  // ── Drag & drop ────────────────────────────────────────────────────────────

  const handleEventDrop = async ({ event, revert }: EventDropArg) => {
    const id = Number(event.id)
    try {
      const updated = await calendarService.rescheduleAppointment(
        id,
        event.startStr,
        event.endStr ?? event.startStr
      )
      updateEvent(event.id, updated)
      toast.success('Cita reagendada')
    } catch (error) {
      revert()
      toast.error(getErrorMessage(error))
    }
  }

  // ── Resize (change duration) ───────────────────────────────────────────────

  const handleEventResize = async ({ event, revert }: EventResizeDoneArg) => {
    const id = Number(event.id)
    try {
      const updated = await calendarService.rescheduleAppointment(
        id,
        event.startStr,
        event.endStr ?? event.startStr
      )
      updateEvent(event.id, updated)
      toast.success('Duración actualizada')
    } catch (error) {
      revert()
      toast.error(getErrorMessage(error))
    }
  }

  // ── Click on existing event ────────────────────────────────────────────────

  const handleEventClick = ({ event }: EventClickArg) => {
    const calEvent = events.find((e) => e.id === event.id) ?? null
    setSelectedEvent(calEvent)
  }

  // ── Click on empty slot → new appointment ─────────────────────────────────

  const handleDateSelect = ({ startStr, endStr }: DateSelectArg) => {
    openCreateForm({ start: startStr, end: endStr })
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full p-4 sm:p-6">
      <CalendarToolbar
        title={getTitle()}
        currentView={view}
        connections={connections}
        agents={agents}
        selectedAgentId={filters.agentId}
        showAgentFilter={canSeeAllAgents}
        onPrev={handlePrev}
        onNext={handleNext}
        onToday={handleToday}
        onViewChange={handleViewChange}
        onNewAppointment={() => openCreateForm()}
        onAgentChange={handleAgentChange}
      />

      {/* Calendar connection panel toggle */}
      <div className="mb-3">
        <button
          onClick={() => setShowConnectionPanel((v) => !v)}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-700 transition-colors"
        >
          <Settings className="h-3.5 w-3.5" />
          {showConnectionPanel ? 'Ocultar calendarios conectados' : 'Gestionar calendarios conectados'}
        </button>

        {showConnectionPanel && (
          <div className="mt-3 p-4 rounded-lg border border-slate-200 bg-slate-50">
            <CalendarConnectionPanel />
          </div>
        )}
      </div>

      {/* Loading overlay */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-slate-800" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && events.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <p className="text-4xl mb-3">📅</p>
          <p className="font-medium text-slate-700">No hay citas en este período</p>
          <p className="text-sm text-slate-400 mb-4">
            Haz clic en un horario del calendario para crear una nueva cita.
          </p>
          <button
            onClick={() => openCreateForm()}
            className="text-sm text-blue-600 hover:underline"
          >
            + Nueva cita
          </button>
        </div>
      )}

      <div className={isLoading ? 'opacity-50 pointer-events-none' : ''}>
        <FullCalendar
          ref={calendarRef}
          plugins={[dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin]}
          initialView={view}
          locale="es"
          timeZone="America/Santiago"
          headerToolbar={false}
          events={events}
          editable={true}
          selectable={true}
          selectMirror={true}
          eventDurationEditable={true}
          eventResizableFromStart={false}
          eventContent={(info: EventContentArg) => <CalendarEventChip eventInfo={info} />}
          eventClick={handleEventClick}
          eventDrop={handleEventDrop}
          eventResize={handleEventResize}
          select={handleDateSelect}
          height="calc(100vh - 260px)"
          slotMinTime="07:00:00"
          slotMaxTime="21:00:00"
          allDaySlot={false}
          nowIndicator={true}
          businessHours={{
            daysOfWeek: [1, 2, 3, 4, 5],
            startTime: '09:00',
            endTime: '18:00',
          }}
          eventConstraint={{ startTime: '07:00', endTime: '21:00' }}
        />
      </div>

      {/* Detail modal — opens when an event is clicked */}
      <AppointmentDetailModal
        onClose={() => setSelectedEvent(null)}
        onDelete={(id) => removeEvent(String(id))}
        onUpdate={(id, data) => updateEvent(String(id), data)}
      />

      {/* Create/Edit modal */}
      <AppointmentFormModal onSaved={fetchEvents} />
    </div>
  )
}

