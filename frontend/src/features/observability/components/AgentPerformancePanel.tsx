import { useEffect } from 'react'
import { Badge } from '@/shared/components/ui/badge'
import { useObservabilityStore } from '../store/observabilityStore'
import type { ObservabilityPeriod } from '../types/observability.types'

const PERIODS: { label: string; value: ObservabilityPeriod }[] = [
  { label: '1h', value: '1h' },
  { label: '24h', value: '24h' },
  { label: '7d', value: '7d' },
  { label: '30d', value: '30d' },
]

const AGENT_STYLE: Record<string, { label: string; className: string }> = {
  qualifier: { label: 'Calificador', className: 'bg-blue-100 text-blue-700 border-blue-200' },
  scheduler: { label: 'Agendador', className: 'bg-green-100 text-green-700 border-green-200' },
  followup: { label: 'Seguimiento', className: 'bg-yellow-100 text-yellow-700 border-yellow-200' },
  property: { label: 'Propiedades', className: 'bg-purple-100 text-purple-700 border-purple-200' },
  human: { label: 'Humano', className: 'bg-slate-100 text-slate-700 border-slate-200' },
}

function latencyColor(ms: number) {
  if (ms < 1000) return 'text-green-600'
  if (ms < 3000) return 'text-yellow-600'
  return 'text-red-600'
}

export function AgentPerformancePanel() {
  const { agentPerformance, agentPeriod, isLoadingAgents, fetchAgentPerformance, setAgentPeriod } =
    useObservabilityStore()

  useEffect(() => {
    fetchAgentPerformance()
  }, [fetchAgentPerformance])

  const agents = agentPerformance?.agents ?? []

  return (
    <div className="space-y-4">
      {/* Header with period selector */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">Rendimiento por agente</h2>
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setAgentPeriod(p.value)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                agentPeriod === p.value
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        {isLoadingAgents && agents.length === 0 ? (
          <div className="space-y-0">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-14 bg-slate-50 animate-pulse border-b border-slate-100" />
            ))}
          </div>
        ) : agents.length === 0 ? (
          <div className="py-16 text-center text-sm text-slate-400">
            Sin datos para el período seleccionado
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Agente
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Mensajes
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  P50 (ms)
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  P95 (ms)
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Tokens/resp
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Costo/resp
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Handoffs
                </th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                  Errores
                </th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => {
                const style = AGENT_STYLE[agent.agent_type] ?? {
                  label: agent.agent_type,
                  className: 'bg-slate-100 text-slate-700 border-slate-200',
                }
                return (
                  <tr
                    key={agent.agent_type}
                    className="border-b border-slate-100 hover:bg-slate-50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <Badge className={`text-xs border ${style.className}`}>
                        {style.label}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-slate-900">
                      {agent.messages_handled.toLocaleString()}
                    </td>
                    <td className={`px-4 py-3 text-right font-mono ${latencyColor(agent.p50_latency_ms)}`}>
                      {agent.p50_latency_ms.toLocaleString()}
                    </td>
                    <td className={`px-4 py-3 text-right font-mono ${latencyColor(agent.p95_latency_ms)}`}>
                      {agent.p95_latency_ms.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">
                      {agent.avg_tokens.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700 font-mono">
                      ${agent.avg_cost_usd.toFixed(5)}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">
                      {agent.handoffs_out}
                    </td>
                    <td
                      className={`px-4 py-3 text-right font-medium ${
                        agent.error_count > 0 ? 'text-red-600' : 'text-slate-400'
                      }`}
                    >
                      {agent.error_count}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
