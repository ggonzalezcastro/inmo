import { CheckCircle, XCircle, Wifi } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import type { SystemHealth } from '../types/superAdmin.types'

interface Props {
  health: SystemHealth
}

function StatusBadge({ value }: { value: string }) {
  const ok = value === 'ok'
  const Icon = ok ? CheckCircle : XCircle
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${ok ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
      <Icon size={11} />
      {ok ? 'OK' : value}
    </span>
  )
}

function BreakerBadge({ state }: { state: string }) {
  const colorMap: Record<string, string> = {
    closed: 'bg-green-100 text-green-700',
    open: 'bg-red-100 text-red-700',
    half_open: 'bg-yellow-100 text-yellow-700',
  }
  const cls = colorMap[state] ?? 'bg-slate-100 text-slate-600'
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${cls}`}>{state}</span>
  )
}

export function SystemHealthPanel({ health }: Props) {
  const { database, redis, circuit_breakers, semantic_cache, prompt_cache, websocket } = health

  const wsData = Object.entries(websocket.by_broker_named ?? websocket.by_broker ?? {}).map(
    ([name, count]) => ({ name, count })
  )

  const hitRate = typeof semantic_cache?.hit_rate === 'number'
    ? Math.round(semantic_cache.hit_rate * 100)
    : null

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Infrastructure */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3">
        <h3 className="text-sm font-semibold text-slate-700">Infraestructura</h3>
        <div className="flex justify-between items-center">
          <span className="text-sm text-slate-600">Base de datos</span>
          <StatusBadge value={database} />
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-slate-600">Redis</span>
          <StatusBadge value={redis} />
        </div>
        {hitRate !== null && (
          <div className="space-y-1">
            <div className="flex justify-between text-sm text-slate-600">
              <span>Semantic cache hit rate</span>
              <span className="font-medium">{hitRate}%</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full"
                style={{ width: `${hitRate}%` }}
              />
            </div>
          </div>
        )}
        {typeof prompt_cache?.active_entries === 'number' && (
          <div className="flex justify-between items-center">
            <span className="text-sm text-slate-600">Prompt cache entries</span>
            <span className="text-sm font-medium text-slate-800">{prompt_cache.active_entries}</span>
          </div>
        )}
      </div>

      {/* Circuit Breakers */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3">
        <h3 className="text-sm font-semibold text-slate-700">Circuit Breakers</h3>
        {Object.keys(circuit_breakers).length === 0 ? (
          <p className="text-xs text-slate-400">Sin circuit breakers registrados</p>
        ) : (
          Object.entries(circuit_breakers).map(([name, state]) => (
            <div key={name} className="flex justify-between items-center">
              <span className="text-sm text-slate-600 font-mono">{name}</span>
              <BreakerBadge state={state} />
            </div>
          ))
        )}
      </div>

      {/* WebSocket Connections */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 space-y-3 md:col-span-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">WebSocket Connections</h3>
          <span className="inline-flex items-center gap-1 text-xs text-slate-500">
            <Wifi size={12} />
            {websocket.total_connections} total
          </span>
        </div>
        {wsData.length === 0 ? (
          <p className="text-xs text-slate-400">Sin conexiones activas</p>
        ) : (
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={wsData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#1A56DB" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
