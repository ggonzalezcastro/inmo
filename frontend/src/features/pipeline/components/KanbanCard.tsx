import { useState } from 'react'
import { Clock, User, Bot, AlertTriangle, CalendarCheck, CheckCircle2 } from 'lucide-react'
import { cn } from '@/shared/lib/utils'
import { StatusBadge } from '@/shared/components/common/StatusBadge'
import { ScoreBadge } from '@/shared/components/common/ScoreBadge'
import { QualificationBadge } from '@/shared/components/common/QualificationBadge'
import { formatRelativeTime } from '@/shared/lib/utils'
import type { Lead } from '@/features/leads/types'
import type { IncomeTier } from '@/features/settings/services/settings.service'
import { conversationService } from '@/features/conversations/services/conversation.service'

interface KanbanCardProps {
  lead: Lead
  isInactive?: boolean
  incomeTiers?: IncomeTier[]
  onClick?: () => void
}

function getIncomeTierLabel(income: number | undefined, tiers: IncomeTier[]): string | null {
  if (!income || !tiers.length) return null
  const sorted = [...tiers].sort((a, b) => b.min - a.min)
  for (const tier of sorted) {
    if (income >= tier.min && tier.points > 0) return tier.label
  }
  return null
}

export function KanbanCard({ lead, isInactive, incomeTiers, onClick }: KanbanCardProps) {
  // Pipeline API returns "metadata", leads API returns "lead_metadata" — handle both
  const meta = (lead as any).metadata ?? lead.lead_metadata ?? {}
  const isHotFastTrack = Boolean(meta.hot_fast_track)
  const isFrustrated = Boolean(meta.sentiment?.escalated)
  const [humanMode, setHumanMode] = useState(Boolean(meta.human_mode))

  const highlights: string[] = []
  if (meta.dicom_status === 'clean') highlights.push('Sin DICOM')
  if (meta.response_metrics?.is_fast_responder === true) highlights.push('Responde rápido')
  const tierLabel = incomeTiers ? getIncomeTierLabel(meta.monthly_income, incomeTiers) : null
  if (tierLabel) highlights.push(tierLabel)
  const showHighlights =
    highlights.length > 0 &&
    (meta.calificacion === 'CALIFICADO' || (lead.lead_score ?? 0) >= 65)
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
      setHumanMode(humanMode) // Revert optimistic update on API failure
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
        isFrustrated
          ? 'border-red-300 bg-red-50/40 hover:border-red-400'
          : humanMode
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
          {isFrustrated && (
            <span title="Lead frustrado — requiere atención humana" className="text-base leading-none">
              🚨
            </span>
          )}
          {!isFrustrated && isHotFastTrack && (
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
        {isFrustrated && (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-red-100 text-red-700 border border-red-200">
            <AlertTriangle className="h-2.5 w-2.5" /> Frustrado
          </span>
        )}
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

      {/* Qualification highlights */}
      {showHighlights && (
        <div className="flex flex-wrap gap-1">
          {highlights.map((h) => (
            <span
              key={h}
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200"
            >
              <CheckCircle2 className="h-2.5 w-2.5" /> {h}
            </span>
          ))}
        </div>
      )}

      {/* Next appointment badge for agendado leads */}
      {lead.next_appointment && (lead.next_appointment.status === 'scheduled' || lead.next_appointment.status === 'confirmed') && (
        <div className="flex items-center gap-1.5 text-xs text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-md px-2 py-1">
          <CalendarCheck className="h-3 w-3 shrink-0" />
          <span className="truncate">
            {new Date(lead.next_appointment.start_time).toLocaleDateString('es-CL', { day: 'numeric', month: 'short' })}
            {' · '}
            {new Date(lead.next_appointment.start_time).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      )}

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
