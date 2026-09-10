import { CircleHelp, PhoneCall, PhoneMissed, PhoneOff, Radio } from 'lucide-react'
import type { ContactabilityMetrics } from '../types'

interface ContactabilityBadgeProps {
  contactability?: ContactabilityMetrics | null
  showScore?: boolean
}

const CONFIG = {
  contactable: {
    label: 'Contactable',
    className: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: PhoneCall,
  },
  intermittent: {
    label: 'Intermitente',
    className: 'bg-amber-50 text-amber-700 border-amber-200',
    icon: Radio,
  },
  difficult: {
    label: 'Difícil',
    className: 'bg-orange-50 text-orange-700 border-orange-200',
    icon: PhoneMissed,
  },
  critical: {
    label: 'Crítico',
    className: 'bg-rose-50 text-rose-700 border-rose-200',
    icon: PhoneOff,
  },
  insufficient_data: {
    label: 'Sin información',
    className: 'bg-slate-50 text-slate-600 border-slate-200',
    icon: CircleHelp,
  },
  not_applicable: {
    label: 'No aplica',
    className: 'bg-slate-50 text-slate-500 border-slate-200',
    icon: CircleHelp,
  },
} as const

export function ContactabilityBadge({ contactability, showScore = false }: ContactabilityBadgeProps) {
  if (!contactability) return <span className="text-xs text-muted-foreground">—</span>
  const config = CONFIG[contactability.level]
  const Icon = config.icon

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] font-semibold whitespace-nowrap ${config.className}`}
      title={contactability.reasons.join(' · ')}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {config.label}
      {showScore && contactability.score != null && (
        <span className="opacity-70 tabular-nums">· {contactability.score}</span>
      )}
    </span>
  )
}
