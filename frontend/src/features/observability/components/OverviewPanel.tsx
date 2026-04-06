import { useEffect } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  BarChart,
  Bar,
} from 'recharts'
import { useObservabilityStore } from '../store/observabilityStore'
import type { ObservabilityPeriod } from '../types/observability.types'

const PERIODS: { label: string; value: ObservabilityPeriod }[] = [
  { label: '1h', value: '1h' },
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

const PIE_COLORS = ['#3b82f6', '#22c55e', '#eab308', '#a855f7', '#94a3b8', '#f97316']

function MetricCard({
  label,
  value,
  sub,
  color = 'text-slate-900',
}: {
  label: string
  value: string | number
  sub?: string
  color?: string
}) {
  return (
    <div className="rounded-xl border border-slate-200 p-4 bg-white">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  )
}

function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`bg-slate-100 animate-pulse rounded-xl ${className}`} />
}

export function OverviewPanel() {
  const { overview, overviewPeriod, isLoadingOverview, overviewError, fetchOverview, setOverviewPeriod } =
    useObservabilityStore()

  useEffect(() => {
    fetchOverview()
    const interval = setInterval(fetchOverview, 30_000)
    return () => clearInterval(interval)
  }, [fetchOverview])

  const chartData = (overview?.messages_by_hour ?? []).map((item) => ({
    ...item,
    hora: new Date(item.hour).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' }),
  }))

  const pieData = overview?.agent_distribution ?? []
  const funnelData = (overview?.pipeline_funnel ?? []).map((item) => ({
    etapa: item.stage,
    cantidad: item.count,
  }))

  return (
    <div className="space-y-6">
      {/* Period selector */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">Vista general del sistema</h2>
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setOverviewPeriod(p.value)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                overviewPeriod === p.value
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {overviewError && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {overviewError}
        </div>
      )}

      {/* Metric cards */}
      {isLoadingOverview && !overview ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : overview ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label="Conversaciones activas"
            value={overview.active_conversations}
          />
          <MetricCard
            label="Costo LLM"
            value={`$${overview.llm_cost_usd.toFixed(4)}`}
            sub="USD en el período"
          />
          <MetricCard
            label="Tiempo resp. promedio"
            value={`${Math.round(overview.avg_response_time_ms)} ms`}
          />
          <MetricCard
            label="Tasa de escalación"
            value={`${overview.escalation_rate_pct.toFixed(1)}%`}
            color={overview.escalation_rate_pct > 20 ? 'text-red-600' : 'text-slate-900'}
          />
          <MetricCard
            label="Leads en modo humano"
            value={overview.leads_in_human_mode}
            color={overview.leads_in_human_mode > 0 ? 'text-yellow-600' : 'text-slate-900'}
          />
          <MetricCard
            label="Modo humano inactivo"
            value={overview.leads_human_mode_stale}
            sub=">24h sin actividad"
            color={overview.leads_human_mode_stale > 0 ? 'text-orange-600' : 'text-slate-900'}
          />
          <MetricCard
            label="Fallbacks LLM"
            value={overview.fallback_count}
            color={overview.fallback_count > 5 ? 'text-orange-600' : 'text-slate-900'}
          />
          <MetricCard
            label="Errores"
            value={overview.error_count}
            color={overview.error_count > 0 ? 'text-red-600' : 'text-slate-900'}
          />
        </div>
      ) : null}

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Messages by hour area chart */}
        <div className="lg:col-span-2 rounded-xl border border-slate-200 p-4 bg-white">
          <p className="text-sm font-semibold text-slate-900 mb-4">Mensajes por hora</p>
          {isLoadingOverview && !overview ? (
            <Skeleton className="h-48" />
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="hora" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="inbound"
                  name="Entrantes"
                  stroke="#3b82f6"
                  fill="#dbeafe"
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="outbound"
                  name="Salientes"
                  stroke="#22c55e"
                  fill="#dcfce7"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Agent distribution pie */}
        <div className="rounded-xl border border-slate-200 p-4 bg-white">
          <p className="text-sm font-semibold text-slate-900 mb-4">Distribución por agente</p>
          {isLoadingOverview && !overview ? (
            <Skeleton className="h-48" />
          ) : pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="count"
                  nameKey="agent"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  label={({ agent, percent }) =>
                    `${agent} ${(percent * 100).toFixed(0)}%`
                  }
                  labelLine={false}
                >
                  {pieData.map((entry, index) => (
                    <Cell
                      key={entry.agent}
                      fill={AGENT_COLORS[entry.agent] ?? PIE_COLORS[index % PIE_COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-48 flex items-center justify-center text-sm text-slate-400">
              Sin datos
            </div>
          )}
        </div>
      </div>

      {/* Pipeline funnel */}
      <div className="rounded-xl border border-slate-200 p-4 bg-white">
        <p className="text-sm font-semibold text-slate-900 mb-4">Embudo del pipeline</p>
        {isLoadingOverview && !overview ? (
          <Skeleton className="h-48" />
        ) : funnelData.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={funnelData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="etapa" type="category" width={130} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="cantidad" name="Leads" fill="#3b82f6" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-48 flex items-center justify-center text-sm text-slate-400">
            Sin datos de pipeline
          </div>
        )}
      </div>
    </div>
  )
}
