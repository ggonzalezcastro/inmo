import { useEffect, useState } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { useObservabilityStore } from '../store/observabilityStore'
import type { ObservabilityPeriod } from '../types/observability.types'

const PERIODS: { label: string; value: ObservabilityPeriod }[] = [
  { label: '24h', value: '24h' },
  { label: '7d', value: '7d' },
  { label: '30d', value: '30d' },
]

const AGENT_COLORS: Record<string, string> = {
  qualifier: '#3b82f6',
  scheduler: '#22c55e',
  followup: '#eab308',
  property: '#a855f7',
  human: '#94a3b8',
}

type CostTab = 'agente' | 'broker'

function ProjectionCard({
  label,
  value,
  sub,
}: {
  label: string
  value: string
  sub?: string
}) {
  return (
    <div className="rounded-xl border border-slate-200 p-4 bg-white flex-1">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className="text-2xl font-bold text-slate-900">{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  )
}

export function CostAnalysisPanel() {
  const { costByAgent, costByBroker, costProjection, costPeriod, isLoadingCosts, fetchCosts, setCostPeriod } =
    useObservabilityStore()
  const [activeTab, setActiveTab] = useState<CostTab>('agente')

  useEffect(() => {
    fetchCosts()
  }, [fetchCosts])

  const agents = costByAgent?.agents ?? []
  const brokers = costByBroker?.brokers ?? []

  const chartData = agents.map((a) => ({
    agente: a.agent_type,
    costo: parseFloat(a.total_cost_usd.toFixed(5)),
  }))

  return (
    <div className="space-y-6">
      {/* Period + header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">Análisis de costos LLM</h2>
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setCostPeriod(p.value)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                costPeriod === p.value
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Projection cards */}
      {costProjection ? (
        <div className="flex gap-4">
          <ProjectionCard
            label="Costo últimos 7 días"
            value={`$${costProjection.cost_last_7d.toFixed(3)}`}
            sub={costProjection.currency}
          />
          <ProjectionCard
            label="Promedio diario"
            value={`$${costProjection.daily_avg.toFixed(4)}`}
            sub={costProjection.currency}
          />
          <ProjectionCard
            label="Proyección mensual"
            value={`$${costProjection.monthly_projection.toFixed(2)}`}
            sub="estimado"
          />
        </div>
      ) : isLoadingCosts ? (
        <div className="flex gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex-1 h-24 bg-slate-100 animate-pulse rounded-xl" />
          ))}
        </div>
      ) : null}

      {/* Bar chart — by agent */}
      <div className="rounded-xl border border-slate-200 p-4 bg-white">
        <p className="text-sm font-semibold text-slate-900 mb-4">Costo por tipo de agente</p>
        {isLoadingCosts && agents.length === 0 ? (
          <div className="h-48 bg-slate-100 animate-pulse rounded-lg" />
        ) : chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="agente" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
              <Tooltip formatter={(v: number) => [`$${v.toFixed(5)}`, 'Costo USD']} />
              <Bar dataKey="costo" name="Costo USD" radius={[4, 4, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.agente}
                    fill={AGENT_COLORS[entry.agente] ?? '#64748b'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-48 flex items-center justify-center text-sm text-slate-400">
            Sin datos de costo
          </div>
        )}
      </div>

      {/* Detail tables — toggle by agent / by broker */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        {/* Tab switcher */}
        <div className="flex border-b border-slate-200">
          <button
            onClick={() => setActiveTab('agente')}
            className={`px-4 py-2.5 text-xs font-semibold transition-colors ${
              activeTab === 'agente'
                ? 'border-b-2 border-blue-600 text-blue-700'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Por agente
          </button>
          <button
            onClick={() => setActiveTab('broker')}
            className={`px-4 py-2.5 text-xs font-semibold transition-colors ${
              activeTab === 'broker'
                ? 'border-b-2 border-blue-600 text-blue-700'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Por broker
          </button>
        </div>

        {activeTab === 'agente' ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Agente</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Llamadas</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Tokens totales</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Costo total</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Costo/llamada</th>
              </tr>
            </thead>
            <tbody>
              {isLoadingCosts && agents.length === 0
                ? Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={5} className="px-4 py-3">
                        <div className="h-5 bg-slate-100 animate-pulse rounded" />
                      </td>
                    </tr>
                  ))
                : agents.length === 0
                ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-slate-400">Sin datos</td>
                  </tr>
                )
                : agents.map((a) => (
                    <tr key={a.agent_type} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3 font-medium text-slate-900">{a.agent_type}</td>
                      <td className="px-4 py-3 text-right text-slate-700">{a.call_count.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right text-slate-700">{a.total_tokens.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right font-mono text-slate-900">${a.total_cost_usd.toFixed(4)}</td>
                      <td className="px-4 py-3 text-right font-mono text-slate-700">${a.avg_cost_usd.toFixed(5)}</td>
                    </tr>
                  ))}
            </tbody>
          </table>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Broker</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Llamadas</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Leads calificados</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Costo total</th>
                <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Costo/lead</th>
              </tr>
            </thead>
            <tbody>
              {isLoadingCosts && brokers.length === 0
                ? Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={5} className="px-4 py-3">
                        <div className="h-5 bg-slate-100 animate-pulse rounded" />
                      </td>
                    </tr>
                  ))
                : brokers.length === 0
                ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-slate-400">Sin datos de broker</td>
                  </tr>
                )
                : brokers.map((b) => (
                    <tr key={b.broker_id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3 font-medium text-slate-900">
                        {b.broker_name ?? `Broker #${b.broker_id}`}
                      </td>
                      <td className="px-4 py-3 text-right text-slate-700">{b.total_calls.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right text-slate-700">{b.leads_qualified.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right font-mono text-slate-900">${b.total_cost_usd.toFixed(4)}</td>
                      <td className="px-4 py-3 text-right font-mono text-slate-700">
                        {b.cost_per_lead != null ? `$${b.cost_per_lead.toFixed(4)}` : '—'}
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
