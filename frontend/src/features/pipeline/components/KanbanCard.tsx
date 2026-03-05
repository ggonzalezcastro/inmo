import { useState } from 'react'
import { Clock, User, Bot } from 'lucide-react'
import { cn } from '@/shared/lib/utils'
import { StatusBadge } from '@/shared/components/common/StatusBadge'
import { ScoreBadge } from '@/shared/components/common/ScoreBadge'
import { QualificationBadge } from '@/shared/components/common/QualificationBadge'
import { formatRelativeTime } from '@/shared/lib/utils'
import type { Lead } from '@/features/leads/types'
import { conversationService } from '@/features/conversations/services/conversation.service'

interface KanbanCardProps {
  lead: Lead
  isInactive?: boolean
  onClick?: () => void
}

export function KanbanCard({ lead, isInactive, onClick }: KanbanCardProps) {
  const meta = lead.lead_metadata ?? {}
  const isHotFastTrack = Boolean(meta.hot_fast_track)
  const [humanMode, setHumanMode] = useState(Boolean(meta.human_mode))
  const [toggling, setToggling] = useState(false)

  async function handleToggle(e: React.MouseEvent) {
    e.stopPropagation()
    if (toggling) return
    setToggling(true)
    try {
      if (humanMode) {
        await conversationService.release(lead.id)
        setHumanMode(false)
      } else {
        await conversationService.takeover(lead.id)
        setHumanMode(true)
      }
    } catch (err) {
      console.error(err)
    } finally {
      setToggling(false)
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === 'Enter' && onClick?.()}
      className={cn(
        'bg-white rounded-lg border p-3 space-y-2',
        'cursor-pointer select-none',
        humanMode
          ? 'border-[#BFDBFE] bg-[#EFF6FF]/50 hover:border-[#1A56DB]/60'
          : isInactive
          ? 'border-amber-200 bg-amber-50/40 hover:border-amber-300'
          : 'border-border hover:border-[#1A56DB]/40 hover:shadow-sm',
        'transition-all duration-150'
      )}
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex items-center gap-1">
          {isHotFastTrack && (
            <span title="Avanzado automáticamente por ser lead HOT — Sofía debe proponer visita" className="text-base leading-none">
              🔥
            </span>
          )}
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground truncate leading-tight">
              {lead.name}
            </p>
            <p className="text-xs text-muted-foreground truncate mt-0.5">{lead.phone}</p>
          </div>
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
        {humanMode && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-[#DBEAFE] text-[#1D4ED8]">
            <User className="h-2.5 w-2.5" /> Humano
          </span>
        )}
      </div>

      {/* Last contact */}
      {lead.last_contacted && (
        <p className="text-xs text-muted-foreground">
          Contactado: {formatRelativeTime(lead.last_contacted)}
        </p>
      )}

      {/* Takeover button */}
      <button
        onClick={handleToggle}
        disabled={toggling}
        className={cn(
          'w-full flex items-center justify-center gap-1.5 py-1 rounded-md text-[11px] font-medium transition-colors border',
          humanMode
            ? 'border-[#BFDBFE] text-[#1D4ED8] bg-white hover:bg-[#EFF6FF]'
            : 'border-[#E5E7EB] text-[#6B7280] bg-white hover:bg-[#F3F4F6] hover:text-[#111827]',
        )}
      >
        {humanMode ? (
          <><Bot size={11} /> Liberar a IA</>
        ) : (
          <><User size={11} /> Tomar control</>
        )}
      </button>
    </div>
  )
}
