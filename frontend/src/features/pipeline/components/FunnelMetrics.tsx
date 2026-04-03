import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp, TrendingUp, Clock, XCircle } from 'lucide-react'
import { cn } from '@/shared/lib/utils'
import { pipelineService, type FunnelMetrics as FunnelMetricsData } from '../services/pipeline.service'

const STAGE_LABELS: Record<string, string> = {
  entrada: 'Entrada',
  perfilamiento: 'Perfilamiento',
  calificacion_financiera: 'Cal. Financiera',
  potencial: 'Potencial',
  agendado: 'Agendado',
  ganado: 'Ganado',
  perdido: 'Perdido',
}

const ACTIVE_STAGES = ['entrada', 'perfilamiento', 'calificacion_financiera', 'potencial', 'agendado']

const CONVERSION_PAIRS: Array<[string, string, string]> = [
  ['entrada', 'perfilamiento', 'E→P'],
  ['perfilamiento', 'calificacion_financiera', 'P→CF'],
  ['calificacion_financiera', 'potencial', 'CF→Pot'],
  ['potencial', 'agendado', 'Pot→Ag'],
  ['agendado', 'ganado', 'Ag→G'],
]

function conversionKey(from: string, to: string) {
  return `${from}_to_${to}`
}

interface Props {
  className?: string
}

export function FunnelMetrics({ className }: Props) {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<FunnelMetricsData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open || data) return
    setLoading(true)
    pipelineService.getFunnelMetrics()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [open, data])

  return (
    <div className={cn('border-b bg-background', className)}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-sm font-medium text-foreground hover:bg-muted/40 transition-colors"
      >
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-[#1A56DB]" />
          <span>Métricas del Funnel</span>
          {data && !loading && (
            <span className="text-xs text-muted-foreground font-normal">
              — {data.total_leads} leads · {data.total_conversion_rate}% conversión global
            </span>
          )}
        </div>
        {open ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>

      {open && (
        <div className="px-4 pb-4 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          {loading && (
            <p className="col-span-3 text-muted-foreground text-xs py-2">Cargando métricas…</p>
          )}

          {data && !loading && (
            <>
              {/* Conversion rates */}
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                  Tasas de conversión
                </p>
                <div className="space-y-1.5">
                  {CONVERSION_PAIRS.map(([from, to, shortLabel]) => {
                    const rate = data.conversion_rates[conversionKey(from, to)] ?? 0
                    return (
                      <div key={shortLabel} className="flex items-center gap-2">
                        <span className="w-20 text-xs text-muted-foreground shrink-0">{shortLabel}</span>
                        <div className="flex-1 bg-muted rounded-full h-2 overflow-hidden">
                          <div
                            className="h-full bg-[#1A56DB] rounded-full transition-all"
                            style={{ width: `${Math.min(rate, 100)}%` }}
                          />
                        </div>
                        <span className="w-9 text-right text-xs font-semibold tabular-nums">{rate}%</span>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Avg days per stage */}
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" /> Días promedio en etapa
                </p>
                <div className="space-y-1.5">
                  {ACTIVE_STAGES.map((stage) => {
                    const days = data.avg_stage_days[stage] ?? 0
                    const count = data.stage_counts[stage] ?? 0
                    return (
                      <div key={stage} className="flex items-center justify-between gap-2">
                        <span className="text-xs text-muted-foreground truncate">{STAGE_LABELS[stage]}</span>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-xs text-muted-foreground">({count})</span>
                          <span className="text-xs font-semibold tabular-nums w-12 text-right">
                            {days > 0 ? `${days}d` : '—'}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Lost by stage + summary */}
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2 flex items-center gap-1">
                  <XCircle className="h-3.5 w-3.5 text-red-500" /> Perdidos por etapa
                </p>
                <div className="space-y-1.5">
                  {ACTIVE_STAGES.map((stage) => {
                    const lost = data.lost_by_stage[stage] ?? 0
                    return (
                      <div key={stage} className="flex items-center justify-between gap-2">
                        <span className="text-xs text-muted-foreground">{STAGE_LABELS[stage]}</span>
                        <span className={cn(
                          'text-xs font-semibold tabular-nums',
                          lost > 0 ? 'text-red-600' : 'text-muted-foreground'
                        )}>
                          {lost > 0 ? lost : '—'}
                        </span>
                      </div>
                    )
                  })}
                </div>

                <div className="mt-4 pt-3 border-t">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-muted-foreground">Conversión total</span>
                    <span className="text-sm font-bold text-[#1A56DB]">{data.total_conversion_rate}%</span>
                  </div>
                  <div className="flex justify-between items-center mt-1">
                    <span className="text-xs text-muted-foreground">Total leads</span>
                    <span className="text-sm font-semibold">{data.total_leads}</span>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
