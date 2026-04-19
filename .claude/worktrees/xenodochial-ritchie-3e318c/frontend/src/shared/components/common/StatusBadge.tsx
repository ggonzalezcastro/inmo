import { cn } from '@/shared/lib/utils'
import { LEAD_STATUS_CONFIG } from '@/shared/lib/constants'
import type { LeadStatus } from '@/features/leads/types'

interface StatusBadgeProps {
  status: LeadStatus
  size?: 'sm' | 'md'
  className?: string
}

export function StatusBadge({ status, size = 'md', className }: StatusBadgeProps) {
  const config = LEAD_STATUS_CONFIG[status] ?? { label: status, className: 'bg-slate-100 text-slate-600 border-slate-200' }

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border font-medium',
        config.className,
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-0.5 text-xs',
        className
      )}
    >
      {config.label}
    </span>
  )
}
