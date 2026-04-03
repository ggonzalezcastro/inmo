import { PIPELINE_STAGES } from '@/shared/lib/constants'
import { cn } from '@/shared/lib/utils'

interface StageAvgDaysTableProps {
  stageAvgDays: Record<string, number>
  isLoading: boolean
}

function SpeedBadge({ days }: { days: number }) {
  if (days < 3) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block" />
        Rápido
      </span>
    )
  }
  if (days <= 7) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-700">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />
        Normal
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-600">
      <span className="w-1.5 h-1.5 rounded-full bg-rose-400 inline-block" />
      Lento
    </span>
  )
}

export function StageAvgDaysTable({ stageAvgDays, isLoading }: StageAvgDaysTableProps) {
  const activeStages = PIPELINE_STAGES.filter(
    (s) => s.key !== 'ganado' && s.key !== 'perdido'
  )

  const rows = activeStages
    .map((s) => ({ key: s.key, label: s.label, days: stageAvgDays[s.key] ?? 0 }))
    .sort((a, b) => b.days - a.days)

  return (
    <div className="flex flex-col bg-white border border-[#D1D9E6] rounded-xl shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#E8EEF6]">
        <span className="text-[#111827] text-[14px] font-bold">Tiempo por etapa</span>
        <span className="text-[#9CA3AF] text-[12px]">Promedio de días</span>
      </div>

      <div className="flex flex-col flex-1">
        {isLoading ? (
          <div className="flex flex-col gap-3 p-5">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-8 rounded bg-[#F0F4F8] animate-pulse" />
            ))}
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="grid grid-cols-3 px-5 py-2 border-b border-[#F0F4F8]">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-[#9CA3AF]">Etapa</span>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-[#9CA3AF] text-center">Días prom.</span>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-[#9CA3AF] text-right">Velocidad</span>
            </div>

            {rows.map((row) => (
              <div
                key={row.key}
                className="grid grid-cols-3 items-center px-5 py-2.5 border-b border-[#F0F4F8] last:border-0 hover:bg-[#FAFBFD] transition-colors"
              >
                <span className="text-[13px] text-[#374151] truncate">{row.label}</span>
                <span
                  className={cn(
                    'text-[13px] font-semibold tabular-nums text-center',
                    row.days < 3
                      ? 'text-emerald-600'
                      : row.days <= 7
                      ? 'text-amber-600'
                      : 'text-rose-600'
                  )}
                >
                  {row.days.toFixed(1)}d
                </span>
                <div className="flex justify-end">
                  <SpeedBadge days={row.days} />
                </div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}
