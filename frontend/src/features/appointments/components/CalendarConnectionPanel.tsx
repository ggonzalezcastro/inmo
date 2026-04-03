import { useEffect, useState, useCallback } from 'react'
import { toast } from 'sonner'
import { Link, Unlink, RefreshCw } from 'lucide-react'
import { Button } from '@/shared/components/ui/button'
import { Badge } from '@/shared/components/ui/badge'
import { calendarProvidersService } from '../services/calendarProviders.service'
import { useCalendarStore } from '../store/calendarStore'
import { getErrorMessage } from '@/shared/types/api'
import type { CalendarProvider } from '../types/calendar.types'

interface ProviderCardProps {
  provider: CalendarProvider
  label: string
  icon: string
  connected: boolean
  email?: string
  onConnect: () => void
  onDisconnect: () => void
  loading: boolean
}

function ProviderCard({
  label,
  icon,
  connected,
  email,
  onConnect,
  onDisconnect,
  loading,
}: ProviderCardProps) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-3">
        <span className="text-2xl">{icon}</span>
        <div>
          <p className="font-medium text-slate-800 text-sm">{label}</p>
          {connected && email ? (
            <p className="text-xs text-slate-500">{email}</p>
          ) : (
            <p className="text-xs text-slate-400">No conectado</p>
          )}
        </div>
        <Badge
          variant="outline"
          className={
            connected
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-slate-50 text-slate-500 border-slate-200'
          }
        >
          {connected ? 'Conectado' : 'Desconectado'}
        </Badge>
      </div>

      <div className="shrink-0">
        {connected ? (
          <Button
            size="sm"
            variant="outline"
            className="text-rose-600 border-rose-200 hover:bg-rose-50"
            disabled={loading}
            onClick={onDisconnect}
          >
            <Unlink className="h-4 w-4 mr-1" />
            Desconectar
          </Button>
        ) : (
          <Button size="sm" variant="outline" disabled={loading} onClick={onConnect}>
            <Link className="h-4 w-4 mr-1" />
            Conectar
          </Button>
        )}
      </div>
    </div>
  )
}

/** Opens an OAuth popup and listens for the redirect back to /appointments?connected=<provider> */
function openOAuthPopup(
  authUrl: string,
  onSuccess: (provider: string) => void,
  onError: () => void
) {
  const popup = window.open(authUrl, 'calendar-oauth', 'width=600,height=700')

  if (!popup) {
    onError()
    return
  }

  // Poll for the popup URL to change to our app domain (indicating redirect back)
  const interval = setInterval(() => {
    try {
      if (popup.closed) {
        clearInterval(interval)
        onError()
        return
      }
      const url = popup.location.href
      if (url.includes('/appointments')) {
        clearInterval(interval)
        popup.close()
        const params = new URLSearchParams(url.split('?')[1] ?? '')
        const connected = params.get('connected')
        const error = params.get('error')
        if (connected) {
          onSuccess(connected)
        } else if (error) {
          onError()
        }
      }
    } catch {
      // cross-origin error while popup is at OAuth provider — ignore until redirect
    }
  }, 500)
}

interface CalendarConnectionPanelProps {
  className?: string
}

export function CalendarConnectionPanel({ className }: CalendarConnectionPanelProps) {
  const { connections, setConnections } = useCalendarStore()
  const [loadingProvider, setLoadingProvider] = useState<CalendarProvider | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const refresh = useCallback(async () => {
    setRefreshing(true)
    try {
      const updated = await calendarProvidersService.getStatus()
      setConnections(updated)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setRefreshing(false)
    }
  }, [setConnections])

  // Load status on mount
  useEffect(() => {
    void refresh()
  }, [refresh])

  const handleConnect = async (provider: CalendarProvider) => {
    setLoadingProvider(provider)
    try {
      const authUrl =
        provider === 'google'
          ? await calendarProvidersService.getGoogleAuthUrl()
          : await calendarProvidersService.getOutlookAuthUrl()

      openOAuthPopup(
        authUrl,
        async (_connected) => {
          toast.success(`${provider === 'google' ? 'Google Calendar' : 'Outlook'} conectado`)
          await refresh()
          setLoadingProvider(null)
        },
        () => {
          toast.error('No se pudo completar la conexión')
          setLoadingProvider(null)
        }
      )
    } catch (error) {
      toast.error(getErrorMessage(error))
      setLoadingProvider(null)
    }
  }

  const handleDisconnect = async (provider: CalendarProvider) => {
    setLoadingProvider(provider)
    try {
      if (provider === 'google') {
        await calendarProvidersService.disconnectGoogle()
      } else {
        await calendarProvidersService.disconnectOutlook()
      }
      toast.success(`${provider === 'google' ? 'Google Calendar' : 'Outlook'} desconectado`)
      await refresh()
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setLoadingProvider(null)
    }
  }

  const googleConn = connections.find((c) => c.provider === 'google')
  const outlookConn = connections.find((c) => c.provider === 'outlook')

  return (
    <div className={className}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="font-medium text-slate-800">Calendarios conectados</h3>
          <p className="text-xs text-slate-500">
            Las citas se sincronizan automáticamente con tu calendario personal.
          </p>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={refresh}
          disabled={refreshing}
          aria-label="Actualizar estado"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      <div className="space-y-3">
        <ProviderCard
          provider="google"
          label="Google Calendar"
          icon="🔵"
          connected={googleConn?.connected ?? false}
          email={googleConn?.email}
          loading={loadingProvider === 'google'}
          onConnect={() => handleConnect('google')}
          onDisconnect={() => handleDisconnect('google')}
        />
        <ProviderCard
          provider="outlook"
          label="Outlook / Microsoft 365"
          icon="🔷"
          connected={outlookConn?.connected ?? false}
          email={outlookConn?.email}
          loading={loadingProvider === 'outlook'}
          onConnect={() => handleConnect('outlook')}
          onDisconnect={() => handleDisconnect('outlook')}
        />
      </div>
    </div>
  )
}
