import { useEffect } from 'react'
import { useObservabilityStore } from '../store/observabilityStore'
import type { ObservabilityPeriod } from '../types/observability.types'

const PERIODS: { label: string; value: ObservabilityPeriod }[] = [
  { label: '24h', value: '24h' },
  { label: '7d', value: '7d' },
  { label: '30d', value: '30d' },
]

function frustrationColor(score: number) {
  if (score >= 0.7) return 'text-red-600 font-semibold'
  if (score >= 0.4) return 'text-yellow-600'
  return 'text-green-600'
}

export function HandoffMonitor() {
  const {
    handoffFlow,
    handoffEscalations,
    handoffPeriod,
    isLoadingHandoffs,
    fetchHandoffs,
    setHandoffPeriod,
  } = useObservabilityStore()

  useEffect(() => {
    fetchHandoffs()
  }, [fetchHandoffs])

  const flows = handoffFlow?.flows ?? []
  const escalations = handoffEscalations?.escalations ?? []

  return (
    <div className="space-y-6">
      {/* Header + period */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">Monitor de handoffs</h2>
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setHandoffPeriod(p.value)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                handoffPeriod === p.value
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Flow table */}
        <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200">
            <h3 className="text-sm font-semibold text-slate-900">Flujo de handoffs</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Desde
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Hacia
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Cantidad
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoadingHandoffs && flows.length === 0 ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={3} className="px-4 py-3">
                      <div className="h-4 bg-slate-100 animate-pulse rounded" />
                    </td>
                  </tr>
                ))
              ) : flows.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-sm text-slate-400">
                    Sin handoffs en el período
                  </td>
                </tr>
              ) : (
                flows
                  .sort((a, b) => b.count - a.count)
                  .map((flow, i) => (
                    <tr
                      key={i}
                      className="border-b border-slate-100 hover:bg-slate-50 transition-colors"
                    >
                      <td className="px-4 py-3 text-slate-700">{flow.from_agent}</td>
                      <td className="px-4 py-3 text-slate-700">{flow.to_agent}</td>
                      <td className="px-4 py-3 text-right font-semibold text-slate-900">
                        {flow.count}
                      </td>
                    </tr>
                  ))
              )}
            </tbody>
          </table>
        </div>

        {/* Escalations table */}
        <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200">
            <h3 className="text-sm font-semibold text-slate-900">Escalaciones recientes</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Lead
                </th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Razón
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Frustración
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Hora
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoadingHandoffs && escalations.length === 0 ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={4} className="px-4 py-3">
                      <div className="h-4 bg-slate-100 animate-pulse rounded" />
                    </td>
                  </tr>
                ))
              ) : escalations.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-sm text-slate-400">
                    Sin escalaciones en el período
                  </td>
                </tr>
              ) : (
                escalations.map((esc, i) => (
                  <tr
                    key={i}
                    className="border-b border-slate-100 hover:bg-slate-50 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-slate-900 truncate max-w-[120px]">
                      {esc.lead_name}
                    </td>
                    <td className="px-4 py-3 text-slate-600 truncate max-w-[140px]">
                      {esc.reason}
                    </td>
                    <td className={`px-4 py-3 text-right ${frustrationColor(esc.frustration_score)}`}>
                      {(esc.frustration_score * 100).toFixed(0)}%
                    </td>
                    <td className="px-4 py-3 text-right text-slate-400 text-xs">
                      {new Date(esc.timestamp).toLocaleTimeString('es-CL', {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
