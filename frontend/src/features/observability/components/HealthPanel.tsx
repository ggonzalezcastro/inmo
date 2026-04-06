import { useEffect } from 'react'
import { useObservabilityStore } from '../store/observabilityStore'
import type { ComponentStatus } from '../types/observability.types'

const COMPONENT_LABELS: Record<string, string> = {
  postgresql: 'PostgreSQL',
  postgres: 'PostgreSQL',
  redis: 'Redis',
  celery: 'Celery',
  ext_gemini: 'Gemini API',
  gemini: 'Gemini API',
  ext_telegram: 'Telegram API',
  telegram: 'Telegram API',
  ext_openai: 'OpenAI API',
  ext_claude: 'Claude API',
}

function StatusDot({ status }: { status: ComponentStatus }) {
  const cls =
    status === 'ok'
      ? 'bg-green-500'
      : status === 'degraded'
      ? 'bg-yellow-400'
      : status === 'error'
      ? 'bg-red-500'
      : 'bg-slate-300'
  return (
    <span className="relative flex h-3 w-3">
      {status === 'ok' && (
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-50" />
      )}
      <span className={`relative inline-flex rounded-full h-3 w-3 ${cls}`} />
    </span>
  )
}

function statusText(status: ComponentStatus) {
  return status === 'ok'
    ? 'Operativo'
    : status === 'degraded'
    ? 'Degradado'
    : status === 'error'
    ? 'Error'
    : 'Desconocido'
}

function statusTextColor(status: ComponentStatus) {
  return status === 'ok'
    ? 'text-green-600'
    : status === 'degraded'
    ? 'text-yellow-600'
    : status === 'error'
    ? 'text-red-600'
    : 'text-slate-400'
}

export function HealthPanel() {
  const { health, isLoadingHealth, fetchHealth } = useObservabilityStore()

  useEffect(() => {
    fetchHealth()
    const interval = setInterval(fetchHealth, 10_000)
    return () => clearInterval(interval)
  }, [fetchHealth])

  const overallStatus = health?.status ?? 'unknown'

  return (
    <div className="space-y-6">
      {/* Overall status banner */}
      <div
        className={`rounded-xl border p-4 flex items-center gap-3 ${
          overallStatus === 'ok'
            ? 'border-green-200 bg-green-50'
            : overallStatus === 'degraded'
            ? 'border-yellow-200 bg-yellow-50'
            : overallStatus === 'error'
            ? 'border-red-200 bg-red-50'
            : 'border-slate-200 bg-slate-50'
        }`}
      >
        <StatusDot status={overallStatus} />
        <div>
          <p className={`text-sm font-semibold ${statusTextColor(overallStatus)}`}>
            Sistema: {statusText(overallStatus)}
          </p>
          {health?.checked_at && (
            <p className="text-xs text-slate-400">
              Actualizado: {new Date(health.checked_at).toLocaleTimeString('es-CL')}
            </p>
          )}
        </div>
      </div>

      {/* Component grid */}
      {isLoadingHealth && !health ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-28 bg-slate-100 animate-pulse rounded-xl" />
          ))}
        </div>
      ) : (health?.components ?? []).length === 0 ? (
        <div className="rounded-xl border border-slate-200 py-16 text-center">
          <p className="text-sm text-slate-400">Sin información de componentes</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {(health?.components ?? []).map((comp) => (
            <div
              key={comp.name}
              className={`rounded-xl border p-4 bg-white ${
                comp.status === 'error'
                  ? 'border-red-200'
                  : comp.status === 'degraded'
                  ? 'border-yellow-200'
                  : 'border-slate-200'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-semibold text-slate-900">
                  {COMPONENT_LABELS[comp.name] ?? comp.name}
                </p>
                <StatusDot status={comp.status} />
              </div>
              <p className={`text-xs font-medium ${statusTextColor(comp.status)}`}>
                {statusText(comp.status)}
              </p>
              {comp.latency_ms != null && (
                <p className="text-xs text-slate-400 mt-1">{comp.latency_ms} ms latencia</p>
              )}
              {comp.message && (
                <p className="text-xs text-slate-500 mt-1 line-clamp-2">{comp.message}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
