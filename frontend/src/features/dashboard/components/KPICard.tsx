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
  trend,
  variant = 'light',
}: KPICardProps) {
  const isDark = variant === 'dark'

  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-xl p-6 flex-1',
        isDark
          ? 'bg-[#1A56DB]'
          : 'bg-white border border-[#D1D9E6]'
      )}
    >
      {/* Label */}
      <span
        className={cn(
          'text-[10px] font-bold uppercase tracking-[1.2px]',
          isDark ? 'text-[#93B4F5]' : 'text-[#9CA3AF]'
        )}
      >
        {title}
      </span>

      {/* Value */}
      <span
        className={cn(
          'text-[32px] font-bold leading-none tabular-nums',
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
