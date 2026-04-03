/**
 * CalendarSection — shows Google and Outlook calendar provider cards side by side.
 * Only one provider can be active at a time. Connecting one disables the other's
 * connect button until the active one is disconnected.
 */
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { CheckCircle2, XCircle, ExternalLink, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { settingsService } from '../services/settings.service'

interface AllCalendarStatus {
  provider: 'google' | 'outlook' | 'none' | null
  google: { connected: boolean; email: string | null }
  outlook: { connected: boolean; email: string | null }
}

// ── Provider card ─────────────────────────────────────────────────────────────

interface ProviderCardProps {
  name: string
  logo: React.ReactNode
  connected: boolean
  email: string | null
  activeProvider: string | null
  onConnect: () => Promise<void>
  onDisconnect: () => Promise<void>
  loading: boolean
}

function ProviderCard({
  name,
  logo,
  connected,
  email,
  activeProvider,
  onConnect,
  onDisconnect,
  loading,
}: ProviderCardProps) {
  const otherProviderActive = activeProvider !== null && !connected

  return (
    <div
      className="flex-1 min-w-[260px] rounded-xl border bg-white p-5 space-y-4"
      style={{ borderColor: '#E5E7EB' }}
    >
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 shrink-0 flex items-center justify-center rounded-lg bg-[#F3F4F6]">
          {logo}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-[#111827]">{name}</p>
          {connected ? (
            <p className="text-xs text-[#6B7280] truncate">{email ?? 'Conectado'}</p>
          ) : (
            <p className="text-xs text-[#9CA3AF]">No conectado</p>
          )}
        </div>
        {connected ? (
          <CheckCircle2 className="h-5 w-5 shrink-0" style={{ color: '#22C55E' }} />
        ) : (
          <XCircle className="h-5 w-5 shrink-0 text-[#D1D5DB]" />
        )}
      </div>

      {/* Status pill */}
      {connected ? (
        <div
          className="flex items-center gap-2 p-2.5 rounded-lg text-xs font-medium"
          style={{ background: '#F0FDF4', border: '1px solid #BBF7D0', color: '#15803D' }}
        >
          <span className="h-2 w-2 rounded-full bg-[#22C55E] shrink-0" />
          Activo — citas se crean aquí automáticamente
        </div>
      ) : otherProviderActive ? (
        <div
          className="flex items-center gap-2 p-2.5 rounded-lg text-xs"
          style={{ background: '#FFFBEB', border: '1px solid #FDE68A', color: '#92400E' }}
        >
          Desconecta el proveedor activo primero para conectar este
        </div>
      ) : null}

      {/* Action button */}
      <div className="pt-1">
        {connected ? (
          <Button variant="destructive" size="sm" onClick={onDisconnect} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
            Desconectar
          </Button>
        ) : (
          <Button
            variant="default"
            size="sm"
            onClick={onConnect}
            disabled={loading || otherProviderActive}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            ) : (
              <ExternalLink className="h-4 w-4 mr-2" />
            )}
            Conectar {name}
          </Button>
        )}
      </div>
    </div>
  )
}

// ── Google logo (inline SVG) ──────────────────────────────────────────────────

function GoogleLogo() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  )
}

// ── Microsoft logo (inline SVG) ───────────────────────────────────────────────

function MicrosoftLogo() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
      <rect x="1" y="1" width="10" height="10" fill="#F25022" />
      <rect x="13" y="1" width="10" height="10" fill="#7FBA00" />
      <rect x="1" y="13" width="10" height="10" fill="#00A4EF" />
      <rect x="13" y="13" width="10" height="10" fill="#FFB900" />
    </svg>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export function CalendarSection() {
  const navigate = useNavigate()
  const location = useLocation()

  const [status, setStatus] = useState<AllCalendarStatus | null>(null)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [outlookLoading, setOutlookLoading] = useState(false)

  const loadStatus = useCallback(() => {
    settingsService
      .getAllCalendarStatus()
      .then(setStatus)
      .catch(() => { /* non-critical */ })
  }, [])

  // Initial load
  useEffect(() => {
    loadStatus()
  }, [loadStatus])

  // Reload when the window regains focus — handles the OAuth popup case where
  // the user authorizes in a popup and returns to this tab without a redirect.
  useEffect(() => {
    window.addEventListener('focus', loadStatus)
    return () => window.removeEventListener('focus', loadStatus)
  }, [loadStatus])

  // Handle post-OAuth redirect (?calendar=google|outlook&status=success|error)
  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const calendar = params.get('calendar')
    const statusParam = params.get('status')

    if (calendar && statusParam) {
      if (statusParam === 'success') {
        const label = calendar === 'outlook' ? 'Outlook Calendar' : 'Google Calendar'
        toast.success(`${label} conectado correctamente`)
        loadStatus()
      } else if (statusParam === 'error') {
        const reason = params.get('reason') ?? 'error desconocido'
        toast.error(`Error al conectar el calendario: ${reason}`)
      }
      // Remove query params from URL
      navigate(location.pathname, { replace: true })
    }
  }, [location.search])

  const activeProvider =
    status?.google.connected
      ? 'google'
      : status?.outlook.connected
      ? 'outlook'
      : null

  const handleConnectGoogle = async () => {
    setGoogleLoading(true)
    try {
      const { auth_url } = await settingsService.getCalendarAuthUrl()
      window.open(auth_url, '_blank', 'width=600,height=700')
    } catch {
      toast.error('No se pudo obtener el enlace de autorización de Google')
    } finally {
      setGoogleLoading(false)
    }
  }

  const handleDisconnectGoogle = async () => {
    setGoogleLoading(true)
    try {
      await settingsService.disconnectCalendar()
      toast.success('Google Calendar desconectado')
      loadStatus()
    } catch {
      toast.error('No se pudo desconectar Google Calendar')
    } finally {
      setGoogleLoading(false)
    }
  }

  const handleConnectOutlook = async () => {
    setOutlookLoading(true)
    try {
      const { auth_url } = await settingsService.getOutlookCalendarAuthUrl()
      window.open(auth_url, '_blank', 'width=600,height=700')
    } catch {
      toast.error('No se pudo obtener el enlace de autorización de Microsoft')
    } finally {
      setOutlookLoading(false)
    }
  }

  const handleDisconnectOutlook = async () => {
    setOutlookLoading(true)
    try {
      await settingsService.disconnectOutlookCalendar()
      toast.success('Outlook Calendar desconectado')
      loadStatus()
    } catch {
      toast.error('No se pudo desconectar Outlook Calendar')
    } finally {
      setOutlookLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-[#6B7280]">
        Conecta el calendario de tu inmobiliaria para crear citas automáticamente con un link de videollamada. Solo puede haber un proveedor activo a la vez.
      </p>

      {/* Provider cards */}
      <div className="flex flex-wrap gap-4">
        <ProviderCard
          name="Google Calendar"
          logo={<GoogleLogo />}
          connected={status?.google.connected ?? false}
          email={status?.google.email ?? null}
          activeProvider={activeProvider}
          onConnect={handleConnectGoogle}
          onDisconnect={handleDisconnectGoogle}
          loading={googleLoading}
        />
        <ProviderCard
          name="Microsoft Outlook"
          logo={<MicrosoftLogo />}
          connected={status?.outlook.connected ?? false}
          email={status?.outlook.email ?? null}
          activeProvider={activeProvider}
          onConnect={handleConnectOutlook}
          onDisconnect={handleDisconnectOutlook}
          loading={outlookLoading}
        />
      </div>

      {/* How it works — shown only when nothing is connected */}
      {!activeProvider && (
        <div
          className="rounded-xl border p-5 space-y-3"
          style={{ borderColor: '#E5E7EB', background: '#FAFAFA' }}
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-[#9CA3AF]">
            Cómo funciona
          </p>
          {[
            'Haz clic en "Conectar" en el proveedor de tu elección',
            'Inicia sesión con la cuenta de tu inmobiliaria',
            'Autoriza el acceso al calendario',
            'Las citas nuevas se crearán automáticamente con un link de reunión',
          ].map((step, i) => (
            <div key={i} className="flex items-start gap-3">
              <span
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold mt-0.5"
                style={{ background: '#DBEAFE', color: '#2563EB' }}
              >
                {i + 1}
              </span>
              <p className="text-sm text-[#374151]">{step}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
