/**
 * CallMetricsCards — aggregate call metrics for the Llamadas page.
 * Data from GET /api/v1/calls/metrics.
 */
import { Loader2 } from 'lucide-react'
import type { CallMetrics } from '../services/pipecat.service'
import { CALL_PURPOSE_LABELS } from '../types'
import type { CallPurpose } from '../types'

function formatDuration(seconds: number | null): string {
  if (!seconds) return '—'
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')} min`
}

const MODE_LABELS: Record<string, string> = {
  autonomous: 'Autónomo',
  copilot: 'Copilot',
  handoff: 'Handoff',
  coaching: 'Coaching',
  ai_agent: 'Agente IA',
  transcriptor: 'Transcriptor',
  unknown: 'Sin modo',
}

export function CallMetricsCards({
  metrics,
  loading,
}: {
  metrics: CallMetrics | null
  loading: boolean
}) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground p-4">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Cargando métricas…
      </div>
    )
  }
  if (!metrics) return null

  const purposeEntries = Object.entries(metrics.by_purpose).filter(([, n]) => n > 0)
  const modeEntries = Object.entries(metrics.by_mode).filter(([, n]) => n > 0)

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div className="rounded-xl border bg-card px-4 py-3">
        <p className="text-2xl font-bold">{metrics.total}</p>
        <p className="text-xs text-muted-foreground">Llamadas totales</p>
      </div>
      <div className="rounded-xl border bg-card px-4 py-3">
        <p className="text-2xl font-bold">{metrics.this_month}</p>
        <p className="text-xs text-muted-foreground">Este mes</p>
      </div>
      <div className="rounded-xl border bg-card px-4 py-3">
        <p className="text-2xl font-bold">{formatDuration(metrics.avg_duration_seconds)}</p>
        <p className="text-xs text-muted-foreground">Duración promedio</p>
      </div>
      <div className="rounded-xl border bg-card px-4 py-3 space-y-0.5 overflow-y-auto max-h-24">
        {purposeEntries.length === 0 && modeEntries.length === 0 ? (
          <p className="text-xs text-muted-foreground">Sin desglose aún</p>
        ) : (
          <>
            {purposeEntries.map(([purpose, n]) => (
              <div key={purpose} className="flex justify-between text-xs">
                <span className="text-muted-foreground truncate">
                  {CALL_PURPOSE_LABELS[purpose as CallPurpose] ?? 'Sin motivo'}
                </span>
                <span className="font-semibold ml-2">{n}</span>
              </div>
            ))}
            {modeEntries.map(([mode, n]) => (
              <div key={mode} className="flex justify-between text-xs">
                <span className="text-muted-foreground truncate">{MODE_LABELS[mode] ?? mode}</span>
                <span className="font-semibold ml-2">{n}</span>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}
