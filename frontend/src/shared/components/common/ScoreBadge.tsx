import { cn } from '@/shared/lib/utils'

interface ScoreBadgeProps {
  score: number
  size?: 'sm' | 'md'
  className?: string
}

function getScoreColor(score: number) {
  if (score >= 80) return 'bg-rose-100 text-rose-700 border-rose-200'
  if (score >= 60) return 'bg-amber-100 text-amber-700 border-amber-200'
  if (score >= 30) return 'bg-blue-100 text-blue-600 border-blue-200'
  return 'bg-slate-100 text-slate-600 border-slate-200'
}

export function ScoreBadge({ score, size = 'md', className }: ScoreBadgeProps) {
  const rounded = Math.round(score)

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border font-semibold tabular-nums',
        getScoreColor(rounded),
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs',
        className
      )}
    >
      {rounded}
    </span>
  )
}
