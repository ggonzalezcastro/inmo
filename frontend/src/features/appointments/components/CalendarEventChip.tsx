import type { EventContentArg } from '@fullcalendar/core'
import type { AppointmentTypeEnum, CalendarProvider } from '../types/calendar.types'
import { APPOINTMENT_TYPE_ICONS } from '../services/calendar.service'

const PROVIDER_ICONS: Record<CalendarProvider, string | null> = {
  google:   '🔵',
  outlook:  '🔷',
  internal: null,
}

interface CalendarEventChipProps {
  eventInfo: EventContentArg
}

export function CalendarEventChip({ eventInfo }: CalendarEventChipProps) {
  const { event, view } = eventInfo
  const props = event.extendedProps
  const typeIcon = APPOINTMENT_TYPE_ICONS[props.appointmentType as AppointmentTypeEnum] ?? '📅'
  const providerIcon = PROVIDER_ICONS[props.provider as CalendarProvider]
  const isMonthView = view.type === 'dayGridMonth'
  const isListView = view.type === 'listWeek'

  if (isListView) {
    return (
      <div className="flex items-center gap-2 py-0.5 w-full">
        <span>{typeIcon}</span>
        <span className="font-medium text-sm truncate">{props.leadName}</span>
        {providerIcon && <span className="text-xs">{providerIcon}</span>}
        {props.agentName && (
          <span className="text-xs text-white/75 ml-auto shrink-0">→ {props.agentName}</span>
        )}
      </div>
    )
  }

  if (isMonthView) {
    return (
      <div className="flex items-center gap-1 px-1 w-full overflow-hidden">
        <span className="text-xs">{typeIcon}</span>
        <span className="text-xs font-medium truncate flex-1">{props.leadName}</span>
        {providerIcon && <span className="text-xs leading-none">{providerIcon}</span>}
      </div>
    )
  }

  // Week / Day view — more detail
  return (
    <div className="px-1 py-0.5 w-full overflow-hidden">
      <div className="flex items-center gap-1">
        <span className="text-sm">{typeIcon}</span>
        <span className="text-sm font-semibold truncate flex-1">{props.leadName}</span>
        {providerIcon && <span className="text-sm leading-none">{providerIcon}</span>}
      </div>
      {props.leadPhone && (
        <div className="text-xs opacity-80 truncate mt-0.5">{props.leadPhone}</div>
      )}
      {props.location && (
        <div className="text-xs opacity-70 truncate">{props.location}</div>
      )}
    </div>
  )
}
