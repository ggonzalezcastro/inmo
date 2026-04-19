import { cn } from '@/shared/lib/utils'
import { PIPELINE_STAGE_CONFIG } from '@/shared/lib/constants'
import type { PipelineStage } from '@/features/leads/types'

interface PipelineStageBadgeProps {
  stage: PipelineStage | string
  size?: 'sm' | 'md'
}

export function PipelineStageBadge({ stage, size = 'md' }: PipelineStageBadgeProps) {
  const config =
    PIPELINE_STAGE_CONFIG[stage as PipelineStage] ??
    { label: stage, color: 'bg-slate-100 text-slate-600 border-slate-200' }

  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border font-medium',
        config.color,
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-0.5 text-xs'
      )}
    >
      {config.label}
    </span>
  )
}
