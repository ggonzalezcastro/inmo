import { PIPELINE_STAGES } from '@/shared/lib/constants'
import type { PipelineMetrics } from '../services/dashboard.service'

interface PipelineSummaryProps {
  metrics: PipelineMetrics | null
  isLoading: boolean
}

const STAGE_DOT_COLORS: Record<string, string> = {
  entrada: '#9CA3AF',
  perfilamiento: '#1A56DB',
  calificacion_financiera: '#F59E0B',
  agendado: '#8B5CF6',
  seguimiento: '#06B6D4',
  referidos: '#10B981',
}

export function PipelineSummary({ metrics, isLoading }: PipelineSummaryProps) {
  const stages = PIPELINE_STAGES.filter((s) => s.key !== 'ganado' && s.key !== 'perdido')
  const total = metrics?.total ?? 0

  return (
    <div className="flex flex-col bg-white border border-[#D1D9E6] rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#E8EEF6]">
        <span className="text-[#111827] text-[14px] font-bold">Estado del Pipeline</span>
        <span className="text-[#9CA3AF] text-[12px]">
          {total} leads totales
        </span>
      </div>

      {/* Content */}
      <div className="flex flex-col gap-0 flex-1">
        {isLoading ? (
          <div className="flex flex-col gap-3 p-5">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-8 rounded bg-[#F0F4F8] animate-pulse" />
            ))}
          </div>
        ) : (
          stages.map((s) => {
            const count = metrics?.stages[s.key]?.count ?? 0
            const pct = total > 0 ? Math.round((count / total) * 100) : 0
            const dotColor = STAGE_DOT_COLORS[s.key] ?? '#C4CDD8'

            return (
              <div
                key={s.key}
                className="flex items-center gap-4 px-5 py-3 border-b border-[#F0F4F8] last:border-0 hover:bg-[#FAFBFD] transition-colors"
              >
                {/* Dot */}
                <div
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: dotColor }}
                />

                {/* Label */}
                <span className="text-[#6B7280] text-[13px] flex-1 min-w-0 truncate">
                  {s.label}
                </span>

                {/* Progress bar */}
                <div className="h-1.5 rounded-full bg-[#F0F4F8] overflow-hidden w-24 shrink-0">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${pct}%`,
                      backgroundColor: dotColor,
                    }}
                  />
                </div>

                {/* Count */}
                <span className="text-[#111827] text-[13px] font-semibold w-6 text-right shrink-0">
                  {count}
                </span>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
