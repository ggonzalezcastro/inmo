import { cn } from '@/shared/lib/utils'
import { CALIFICACION_CONFIG } from '@/shared/lib/constants'
import type { LeadCalificacion } from '@/features/leads/types'

interface QualificationBadgeProps {
  calificacion: LeadCalificacion | string | undefined | null
  size?: 'sm' | 'md'
}

export function QualificationBadge({ calificacion, size = 'md' }: QualificationBadgeProps) {
  if (!calificacion) return null

  const config =
    CALIFICACION_CONFIG[calificacion as LeadCalificacion] ??
    { label: calificacion, className: 'bg-slate-100 text-slate-600 border-slate-200' }

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border font-medium',
        config.className,
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-0.5 text-xs'
      )}
    >
      {config.label}
    </span>
  )
}
