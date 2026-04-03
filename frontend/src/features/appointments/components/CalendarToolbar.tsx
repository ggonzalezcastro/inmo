import { ChevronLeft, ChevronRight, Plus, Link, SlidersHorizontal } from 'lucide-react'
import { Button } from '@/shared/components/ui/button'
import { Badge } from '@/shared/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import type { CalendarViewType, CalendarConnection } from '../types/calendar.types'

interface Agent {
  id: number
  name: string
  email: string
}

interface CalendarToolbarProps {
  title: string
  currentView: CalendarViewType
  connections: CalendarConnection[]
  agents?: Agent[]
  selectedAgentId?: number
  showAgentFilter?: boolean
  onPrev: () => void
  onNext: () => void
  onToday: () => void
  onViewChange: (view: CalendarViewType) => void
  onNewAppointment: () => void
  onAgentChange?: (agentId: number | undefined) => void
}

const VIEWS: { key: CalendarViewType; label: string }[] = [
  { key: 'dayGridMonth', label: 'Mes' },
  { key: 'timeGridWeek', label: 'Semana' },
  { key: 'timeGridDay',  label: 'Día' },
  { key: 'listWeek',     label: 'Agenda' },
]

const PROVIDER_BADGES: Record<string, { label: string; className: string }> = {
  google:  { label: 'Google', className: 'bg-blue-100 text-blue-700 border-blue-200' },
  outlook: { label: 'Outlook', className: 'bg-indigo-100 text-indigo-700 border-indigo-200' },
}

export function CalendarToolbar({
  title,
  currentView,
  connections,
  agents = [],
  selectedAgentId,
  showAgentFilter = false,
  onPrev,
  onNext,
  onToday,
  onViewChange,
  onNewAppointment,
  onAgentChange,
}: CalendarToolbarProps) {
  const connectedProviders = connections.filter((c) => c.connected && c.provider !== 'internal')

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
      {/* Left: navigation */}
      <div className="flex items-center gap-2 flex-wrap">
        <Button variant="outline" size="icon" onClick={onPrev} aria-label="Anterior">
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="sm" onClick={onToday}>
          Hoy
        </Button>
        <Button variant="outline" size="icon" onClick={onNext} aria-label="Siguiente">
          <ChevronRight className="h-4 w-4" />
        </Button>
        <h2 className="text-lg font-semibold text-slate-800 ml-1 capitalize hidden sm:block">
          {title}
        </h2>
      </div>

      {/* Center: view toggle — hidden on mobile (uses agenda by default) */}
      <div className="hidden md:flex items-center rounded-lg border border-slate-200 overflow-hidden">
        {VIEWS.map((v) => (
          <button
            key={v.key}
            onClick={() => onViewChange(v.key)}
            className={[
              'px-3 py-1.5 text-sm font-medium transition-colors',
              currentView === v.key
                ? 'bg-slate-900 text-white'
                : 'bg-white text-slate-600 hover:bg-slate-50',
            ].join(' ')}
          >
            {v.label}
          </button>
        ))}
      </div>

      {/* Right: agent filter (admin only) + providers + new appointment */}
      <div className="flex items-center gap-2 flex-wrap">
        {showAgentFilter && agents.length > 0 && onAgentChange && (
          <div className="flex items-center gap-1.5">
            <SlidersHorizontal className="h-4 w-4 text-slate-400" />
            <Select
              value={selectedAgentId ? String(selectedAgentId) : 'all'}
              onValueChange={(v) => onAgentChange(v === 'all' ? undefined : Number(v))}
            >
              <SelectTrigger className="w-40 h-8 text-sm">
                <SelectValue placeholder="Todos los agentes" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los agentes</SelectItem>
                {agents.map((a) => (
                  <SelectItem key={a.id} value={String(a.id)}>
                    {a.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {connectedProviders.map((c) => {
          const badge = PROVIDER_BADGES[c.provider]
          return badge ? (
            <Badge key={c.provider} variant="outline" className={`hidden sm:flex ${badge.className}`}>
              <Link className="h-3 w-3 mr-1" />
              {c.email ?? badge.label}
            </Badge>
          ) : null
        })}

        <Button onClick={onNewAppointment} size="sm">
          <Plus className="h-4 w-4 mr-1" />
          <span className="hidden sm:inline">Nueva cita</span>
          <span className="sm:hidden">Nueva</span>
        </Button>
      </div>
    </div>
  )
}
