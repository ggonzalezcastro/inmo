import { type LucideIcon } from 'lucide-react'
import { cn } from '@/shared/lib/utils'

interface KPICardProps {
  title: string
  value: string | number
  subtitle?: string
  icon?: LucideIcon
  iconClassName?: string
  trend?: { value: number; label: string }
  variant?: 'light' | 'dark'
}

export function KPICard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  variant = 'light',
}: KPICardProps) {
  const isDark = variant === 'dark'

  return (
    <div
      className={cn(
        'flex flex-col rounded-xl p-6 flex-1 shadow-sm',
        isDark
          ? 'bg-[#1A56DB]'
          : 'bg-white border border-[#D1D9E6]'
      )}
    >
      {/* Icon + Label row */}
      <div className="flex items-center justify-between mb-4">
        <span
          className={cn(
            'text-[10px] font-bold uppercase tracking-[1.2px]',
            isDark ? 'text-[#93B4F5]' : 'text-[#9CA3AF]'
          )}
        >
          {title}
        </span>
        {Icon && (
          <div
            className={cn(
              'w-8 h-8 rounded-lg flex items-center justify-center',
              isDark ? 'bg-white/15' : 'bg-[#EBF2FF]'
            )}
          >
            <Icon className={cn('h-4 w-4', isDark ? 'text-white/80' : 'text-[#1A56DB]')} />
          </div>
        )}
      </div>

      {/* Value */}
      <span
        className={cn(
          'text-[2rem] font-bold leading-none tabular-nums mb-2',
          isDark ? 'text-white' : 'text-[#111827]'
        )}
      >
        {value}
      </span>

      {/* Subtitle / trend */}
      {(subtitle || trend) && (
        <span
          className={cn(
            'text-[12px]',
            isDark ? 'text-[#93B4F5]' : 'text-[#1A56DB]'
          )}
        >
          {trend
            ? `${trend.value >= 0 ? '+' : ''}${trend.value}% ${trend.label}`
            : subtitle}
        </span>
      )}
    </div>
  )
}
