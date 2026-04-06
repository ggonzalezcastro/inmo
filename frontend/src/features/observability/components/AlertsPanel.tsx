import { useEffect } from 'react'
import { AlertTriangle, AlertCircle, Info, Check, Eye, X } from 'lucide-react'
import { Badge } from '@/shared/components/ui/badge'
import { useObservabilityStore } from '../store/observabilityStore'
import type { AlertSeverity, AlertStatus, ObservabilityAlert } from '../types/observability.types'

const SEVERITY_CONFIG: Record<
  AlertSeverity,
  { label: string; icon: React.ReactNode; badgeClass: string; rowClass: string }
> = {
  critical: {
    label: 'Crítico',
    icon: <AlertCircle size={14} />,
    badgeClass: 'bg-red-100 text-red-700 border-red-200',
    rowClass: 'border-l-4 border-l-red-500',
  },
  warning: {
    label: 'Advertencia',
    icon: <AlertTriangle size={14} />,
    badgeClass: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    rowClass: 'border-l-4 border-l-yellow-400',
  },
  info: {
    label: 'Info',
    icon: <Info size={14} />,
    badgeClass: 'bg-blue-100 text-blue-700 border-blue-200',
    rowClass: 'border-l-4 border-l-blue-400',
  },
}

const STATUS_FILTERS: { label: string; value: AlertStatus | 'all' }[] = [
  { label: 'Todas', value: 'all' },
  { label: 'Activas', value: 'active' },
  { label: 'Reconocidas', value: 'acknowledged' },
  { label: 'Resueltas', value: 'resolved' },
]

function AlertCard({ alert }: { alert: ObservabilityAlert }) {
  const { acknowledgeAlert, resolveAlert, dismissAlert } = useObservabilityStore()
  const cfg = SEVERITY_CONFIG[alert.severity]

  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-4 ${cfg.rowClass}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <span className={`flex items-center gap-1 mt-0.5 ${
            alert.severity === 'critical' ? 'text-red-600' :
            alert.severity === 'warning' ? 'text-yellow-600' : 'text-blue-600'
          }`}>
            {cfg.icon}
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <Badge className={`text-xs border ${cfg.badgeClass}`}>{cfg.label}</Badge>
              <span className="text-xs text-slate-400">
                {new Date(alert.created_at).toLocaleString('es-CL')}
              </span>
              {alert.status !== 'active' && (
                <Badge className="text-xs border bg-slate-100 text-slate-500 border-slate-200">
                  {alert.status === 'acknowledged' ? 'Reconocida' :
                   alert.status === 'resolved' ? 'Resuelta' : 'Descartada'}
                </Badge>
              )}
            </div>
            <p className="text-sm font-semibold text-slate-900">{alert.title}</p>
            <p className="text-xs text-slate-500 mt-0.5">{alert.description}</p>
          </div>
        </div>

        {/* Actions */}
        {alert.status === 'active' && (
          <div className="flex gap-1 flex-shrink-0">
            <button
              onClick={() => acknowledgeAlert(alert.id)}
              title="Reconocer"
              className="p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors"
            >
              <Eye size={14} />
            </button>
            <button
              onClick={() => resolveAlert(alert.id)}
              title="Resolver"
              className="p-1.5 rounded-lg text-green-600 hover:bg-green-50 transition-colors"
            >
              <Check size={14} />
            </button>
            <button
              onClick={() => dismissAlert(alert.id)}
              title="Descartar"
              className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export function AlertsPanel() {
  const {
    alerts,
    alertsTotal,
    alertsStatusFilter,
    isLoadingAlerts,
    fetchAlerts,
    setAlertsStatusFilter,
  } = useObservabilityStore()

  useEffect(() => {
    fetchAlerts()
  }, [fetchAlerts])

  const criticalActive = alerts.filter(
    (a) => a.severity === 'critical' && a.status === 'active'
  )

  return (
    <div className="space-y-4">
      {/* Critical banner */}
      {criticalActive.length > 0 && (
        <div className="rounded-xl border border-red-300 bg-red-50 p-4 flex items-center gap-3">
          <AlertCircle size={18} className="text-red-600 flex-shrink-0" />
          <p className="text-sm font-semibold text-red-700">
            {criticalActive.length} alerta{criticalActive.length > 1 ? 's' : ''} crítica
            {criticalActive.length > 1 ? 's' : ''} activa
            {criticalActive.length > 1 ? 's' : ''} — requiere{criticalActive.length > 1 ? 'n' : ''} atención inmediata
          </p>
        </div>
      )}

      {/* Filter + count */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setAlertsStatusFilter(f.value)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                alertsStatusFilter === f.value
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-400">{alertsTotal} alerta{alertsTotal !== 1 ? 's' : ''}</p>
      </div>

      {/* Alert list */}
      {isLoadingAlerts && alerts.length === 0 ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 bg-slate-100 animate-pulse rounded-xl" />
          ))}
        </div>
      ) : alerts.length === 0 ? (
        <div className="rounded-xl border border-slate-200 py-16 text-center">
          <p className="text-sm text-slate-400">Sin alertas para mostrar</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <AlertCard key={alert.id} alert={alert} />
          ))}
        </div>
      )}
    </div>
  )
}
