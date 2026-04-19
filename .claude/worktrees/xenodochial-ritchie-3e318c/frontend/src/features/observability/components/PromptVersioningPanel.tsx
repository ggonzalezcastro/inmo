import { useEffect, useState, useCallback } from 'react'
import { ChevronDown, ChevronRight, CheckCircle2, Circle, RefreshCw, Zap } from 'lucide-react'
import { apiClient } from '@/shared/lib/api-client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Broker {
  id: number
  name: string
  is_active: boolean
}

interface PromptVersion {
  id: number
  version_tag: string
  prompt_type: string | null
  is_active: boolean
  notes: string | null
  content?: string
  total_uses: number
  avg_tokens_per_call: number | null
  avg_latency_ms: number | null
  avg_lead_score_delta: number | null
  escalation_rate: number | null
  created_at: string | null
  created_by: number | null
}

// ── API helpers ───────────────────────────────────────────────────────────────

async function fetchBrokers(): Promise<Broker[]> {
  const res = await apiClient.get<Broker[]>('/api/brokers/')
  return Array.isArray(res) ? res : (res as any).data ?? []
}

async function fetchVersions(brokerId: number): Promise<PromptVersion[]> {
  const res = await apiClient.get<{ versions: PromptVersion[] }>(
    `/api/broker/brokers/${brokerId}/prompts`
  )
  return (res as any).versions ?? []
}

async function activateVersion(brokerId: number, versionId: number): Promise<void> {
  await apiClient.put(`/api/broker/brokers/${brokerId}/prompts/${versionId}/activate`, {})
}

// ── Sub-components ────────────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  system: 'bg-blue-100 text-blue-700',
  qualification: 'bg-green-100 text-green-700',
  scheduling: 'bg-yellow-100 text-yellow-700',
  property: 'bg-purple-100 text-purple-700',
}

function MetricCell({ value, unit, decimals = 1 }: { value: number | null; unit?: string; decimals?: number }) {
  if (value == null) return <span className="text-slate-300">—</span>
  return (
    <span className="font-mono">
      {value.toFixed(decimals)}
      {unit && <span className="text-slate-400 text-xs ml-0.5">{unit}</span>}
    </span>
  )
}

function VersionRow({
  v,
  brokerId,
  onActivate,
}: {
  v: PromptVersion
  brokerId: number
  onActivate: (id: number) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const [activating, setActivating] = useState(false)

  async function handleActivate(e: React.MouseEvent) {
    e.stopPropagation()
    setActivating(true)
    try {
      await activateVersion(brokerId, v.id)
      onActivate(v.id)
    } finally {
      setActivating(false)
    }
  }

  return (
    <>
      <tr
        className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors"
        onClick={() => setExpanded((p) => !p)}
      >
        <td className="px-4 py-3 w-6">
          {expanded ? (
            <ChevronDown size={14} className="text-slate-400" />
          ) : (
            <ChevronRight size={14} className="text-slate-400" />
          )}
        </td>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {v.is_active ? (
              <CheckCircle2 size={15} className="text-green-500 shrink-0" />
            ) : (
              <Circle size={15} className="text-slate-300 shrink-0" />
            )}
            <span className={`font-mono text-sm font-semibold ${v.is_active ? 'text-slate-900' : 'text-slate-600'}`}>
              {v.version_tag}
            </span>
            {v.is_active && (
              <span className="text-xs bg-green-50 text-green-700 border border-green-200 rounded-full px-2 py-0.5">
                activa
              </span>
            )}
          </div>
          {v.notes && <p className="text-xs text-slate-400 mt-0.5 pl-6 truncate max-w-xs">{v.notes}</p>}
        </td>
        <td className="px-4 py-3">
          {v.prompt_type ? (
            <span className={`text-xs rounded-full px-2 py-0.5 font-medium ${TYPE_COLORS[v.prompt_type] ?? 'bg-slate-100 text-slate-600'}`}>
              {v.prompt_type}
            </span>
          ) : (
            <span className="text-slate-300 text-xs">—</span>
          )}
        </td>
        <td className="px-4 py-3 text-right text-slate-700 text-sm">
          {v.total_uses.toLocaleString()}
        </td>
        <td className="px-4 py-3 text-right text-sm">
          <MetricCell value={v.avg_tokens_per_call} unit="tok" decimals={0} />
        </td>
        <td className="px-4 py-3 text-right text-sm">
          <MetricCell value={v.avg_latency_ms} unit="ms" decimals={0} />
        </td>
        <td className="px-4 py-3 text-right text-sm">
          {v.escalation_rate != null ? (
            <span className={v.escalation_rate > 0.2 ? 'text-red-600 font-semibold' : 'text-slate-700'}>
              {(v.escalation_rate * 100).toFixed(1)}%
            </span>
          ) : (
            <span className="text-slate-300">—</span>
          )}
        </td>
        <td className="px-4 py-3 text-right text-xs text-slate-400">
          {v.created_at ? new Date(v.created_at).toLocaleDateString('es-CL') : '—'}
        </td>
        <td className="px-4 py-3 text-right">
          {!v.is_active && (
            <button
              onClick={handleActivate}
              disabled={activating}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 transition-colors disabled:opacity-50 ml-auto"
            >
              <Zap size={11} />
              {activating ? 'Activando…' : 'Activar'}
            </button>
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-slate-100 bg-slate-50">
          <td colSpan={9} className="px-6 pb-4 pt-2">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
              Contenido del prompt
            </p>
            {v.content ? (
              <pre className="text-xs text-slate-700 bg-white border border-slate-200 rounded-lg p-4 overflow-auto max-h-64 whitespace-pre-wrap font-mono leading-relaxed">
                {v.content}
              </pre>
            ) : (
              <p className="text-xs text-slate-400 italic">
                El contenido no está incluido en el listado. Activa esta versión para inspeccionarlo desde la configuración del broker.
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

// ── Main Panel ────────────────────────────────────────────────────────────────

export function PromptVersioningPanel() {
  const [brokers, setBrokers] = useState<Broker[]>([])
  const [selectedBrokerId, setSelectedBrokerId] = useState<number | null>(null)
  const [versions, setVersions] = useState<PromptVersion[]>([])
  const [loadingBrokers, setLoadingBrokers] = useState(true)
  const [loadingVersions, setLoadingVersions] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchBrokers()
      .then((data) => {
        setBrokers(data)
        if (data.length > 0) setSelectedBrokerId(data[0].id)
      })
      .catch(() => setError('No se pudo cargar la lista de brokers'))
      .finally(() => setLoadingBrokers(false))
  }, [])

  const loadVersions = useCallback(async (brokerId: number) => {
    setLoadingVersions(true)
    setError(null)
    try {
      const data = await fetchVersions(brokerId)
      setVersions(data)
    } catch {
      setError('No se pudo cargar las versiones del prompt')
    } finally {
      setLoadingVersions(false)
    }
  }, [])

  useEffect(() => {
    if (selectedBrokerId != null) loadVersions(selectedBrokerId)
  }, [selectedBrokerId, loadVersions])

  function handleActivate(activatedId: number) {
    setVersions((prev) =>
      prev.map((v) => ({ ...v, is_active: v.id === activatedId }))
    )
  }

  const activeBrokerName = brokers.find((b) => b.id === selectedBrokerId)?.name ?? ''

  return (
    <div className="space-y-6">
      {/* Header + broker selector */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">Prompt Versioning</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Compara versiones de prompt, sus métricas de rendimiento y activa la que quieras.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {loadingBrokers ? (
            <div className="h-9 w-52 bg-slate-100 animate-pulse rounded-lg" />
          ) : (
            <select
              value={selectedBrokerId ?? ''}
              onChange={(e) => setSelectedBrokerId(Number(e.target.value))}
              className="h-9 rounded-lg border border-slate-200 px-3 text-sm text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {brokers.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          )}
          <button
            onClick={() => selectedBrokerId != null && loadVersions(selectedBrokerId)}
            disabled={loadingVersions}
            className="flex items-center gap-1.5 h-9 px-3 rounded-lg border border-slate-200 text-sm text-slate-500 hover:text-slate-800 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={13} className={loadingVersions ? 'animate-spin' : ''} />
            Actualizar
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Summary cards */}
      {versions.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500 mb-1">Versiones totales</p>
            <p className="text-2xl font-bold text-slate-900">{versions.length}</p>
            <p className="text-xs text-slate-400 mt-0.5">{activeBrokerName}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500 mb-1">Versión activa</p>
            <p className="text-2xl font-bold text-slate-900">
              {versions.find((v) => v.is_active)?.version_tag ?? '—'}
            </p>
            <p className="text-xs text-slate-400 mt-0.5">en producción ahora</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500 mb-1">Usos versión activa</p>
            <p className="text-2xl font-bold text-slate-900">
              {(versions.find((v) => v.is_active)?.total_uses ?? 0).toLocaleString()}
            </p>
            <p className="text-xs text-slate-400 mt-0.5">llamadas LLM</p>
          </div>
        </div>
      )}

      {/* Versions table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50">
              <th className="w-6 px-4 py-3" />
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Versión
              </th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Tipo
              </th>
              <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Usos
              </th>
              <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Avg tokens
              </th>
              <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Avg latencia
              </th>
              <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Tasa escal.
              </th>
              <th className="text-right px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Creada
              </th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {loadingVersions ? (
              Array.from({ length: 3 }).map((_, i) => (
                <tr key={i}>
                  <td colSpan={9} className="px-4 py-3">
                    <div className="h-5 bg-slate-100 animate-pulse rounded" />
                  </td>
                </tr>
              ))
            ) : versions.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-10 text-center text-sm text-slate-400">
                  No hay versiones de prompt para este broker aún.
                </td>
              </tr>
            ) : (
              versions.map((v) => (
                <VersionRow
                  key={v.id}
                  v={v}
                  brokerId={selectedBrokerId!}
                  onActivate={handleActivate}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-slate-400">
        Las métricas (avg tokens, latencia, tasa de escalación) se actualizan en background cada 5 minutos.
        El contenido completo del prompt se puede ver desde Configuración → Broker.
      </p>
    </div>
  )
}
