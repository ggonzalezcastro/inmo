import { Clock } from 'lucide-react'
import { cn } from '@/shared/lib/utils'
import { StatusBadge } from '@/shared/components/common/StatusBadge'
import { ScoreBadge } from '@/shared/components/common/ScoreBadge'
import { QualificationBadge } from '@/shared/components/common/QualificationBadge'
import { formatRelativeTime } from '@/shared/lib/utils'
import type { Lead } from '@/features/leads/types'

interface KanbanCardProps {
  lead: Lead
  isInactive?: boolean
  onClick?: () => void
}

export function KanbanCard({ lead, isInactive, onClick }: KanbanCardProps) {
  const meta = lead.lead_metadata ?? {}

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === 'Enter' && onClick?.()}
      className={cn(
        'bg-white rounded-lg border p-3 space-y-2',
        'cursor-pointer select-none',
        isInactive
          ? 'border-amber-200 bg-amber-50/40 hover:border-amber-300'
          : 'border-border hover:border-[#1A56DB]/40 hover:shadow-sm',
        'transition-all duration-150'
      )}
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-foreground truncate leading-tight">
            {lead.name}
          </p>
          <p className="text-xs text-muted-foreground truncate mt-0.5">{lead.phone}</p>
        </div>
        <ScoreBadge score={lead.lead_score} size="sm" />
      </div>

      {/* Badges */}
      <div className="flex flex-wrap gap-1">
        <StatusBadge status={lead.status} size="sm" />
        {meta.calificacion && (
          <QualificationBadge calificacion={meta.calificacion as 'CALIFICADO' | 'POTENCIAL' | 'NO_CALIFICADO'} size="sm" />
        )}
        {isInactive && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs bg-amber-100 text-amber-700 border border-amber-200">
            <Clock className="h-3 w-3" />
            Inactivo
          </span>
        )}
      </div>

      {/* Last contact */}
      {lead.last_contacted && (
        <p className="text-xs text-muted-foreground">
          Contactado: {formatRelativeTime(lead.last_contacted)}
        </p>
      )}
    </div>
  )
}
