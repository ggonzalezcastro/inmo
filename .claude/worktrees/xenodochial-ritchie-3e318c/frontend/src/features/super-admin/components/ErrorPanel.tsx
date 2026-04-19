import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, ExternalLink, RefreshCw } from 'lucide-react'
import { apiClient } from '@/shared/lib/api-client'

interface SentryIssue {
  id: string
  short_id: string
  title: string
  level: 'error' | 'warning' | 'info' | 'fatal'
  count: number
  last_seen: string
  first_seen: string
  permalink: string
}

interface ErrorsResponse {
  configured: boolean
  issues: SentryIssue[]
}

const LEVEL_COLORS: Record<string, string> = {
  fatal: 'bg-red-100 text-red-800',
  error: 'bg-orange-100 text-orange-700',
  warning: 'bg-yellow-100 text-yellow-700',
  info: 'bg-blue-100 text-blue-700',
}

function formatRelative(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 60) return `${mins}m`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h`
  return `${Math.floor(hours / 24)}d`
}

export function ErrorPanel() {
  const [data, setData] = useState<ErrorsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetch = async () => {
    setIsLoading(true)
    try {
      const res = await apiClient.get<ErrorsResponse>('/api/v1/admin/errors')
      setData(res)
    } catch {
      // silently fail — Sentry may not be configured
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetch()
    intervalRef.current = setInterval(fetch, 60_000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  if (!data) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-6 flex items-center justify-center h-32">
        {isLoading ? (
          <RefreshCw size={16} className="animate-spin text-slate-400" />
        ) : (
          <p className="text-sm text-slate-400">Cargando errores...</p>
        )}
      </div>
    )
  }

  if (!data.configured) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-6 text-center space-y-2">
        <AlertTriangle size={20} className="mx-auto text-amber-400" />
        <p className="text-sm font-medium text-slate-700">Sentry no configurado</p>
        <p className="text-xs text-slate-400">
          Configura <code className="bg-slate-100 px-1 rounded">SENTRY_DSN</code>,{' '}
          <code className="bg-slate-100 px-1 rounded">SENTRY_AUTH_TOKEN</code>,{' '}
          <code className="bg-slate-100 px-1 rounded">SENTRY_ORG</code> y{' '}
          <code className="bg-slate-100 px-1 rounded">SENTRY_PROJECT</code> en las variables de entorno.
        </p>
      </div>
    )
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
        <h3 className="text-sm font-semibold text-slate-700">Errores Recientes (Sentry)</h3>
        <button
          onClick={fetch}
          disabled={isLoading}
          className="text-slate-400 hover:text-slate-600 disabled:opacity-50"
        >
          <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
        </button>
      </div>

      {data.issues.length === 0 ? (
        <div className="p-6 text-center text-sm text-slate-400">Sin errores — todo limpio 🎉</div>
      ) : (
        <div className="divide-y divide-slate-100">
          {data.issues.map((issue) => (
            <div key={issue.id} className="px-4 py-3 flex items-start gap-3 hover:bg-slate-50">
              <span
                className={`mt-0.5 shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${LEVEL_COLORS[issue.level] ?? 'bg-slate-100 text-slate-600'}`}
              >
                {issue.level}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-slate-800 truncate">{issue.title}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {issue.count} ocurrencias · hace {formatRelative(issue.last_seen)}
                </p>
              </div>
              {issue.permalink && (
                <a
                  href={issue.permalink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 text-slate-300 hover:text-blue-500"
                >
                  <ExternalLink size={13} />
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
