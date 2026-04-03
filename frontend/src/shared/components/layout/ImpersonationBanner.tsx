import { ShieldAlert, X } from 'lucide-react'
import { useAuthStore } from '@/features/auth'
import { apiClient } from '@/shared/lib/api-client'
import { toast } from 'sonner'

export function ImpersonationBanner() {
  const { isImpersonating, impersonatedBrokerName, exitImpersonation } = useAuthStore()

  if (!isImpersonating) return null

  const handleExit = async () => {
    let serverConfirmed = true
    try {
      await apiClient.post('/api/v1/admin/impersonate/exit')
    } catch {
      // Best-effort — restore original token even if server call fails (e.g. token expired)
      serverConfirmed = false
    }
    exitImpersonation()
    if (serverConfirmed) {
      toast.success('Has salido del modo impersonation')
    } else {
      toast.warning('Sesión de impersonation expirada — salida local completada')
    }
  }

  return (
    <div className="sticky top-0 z-50 flex items-center gap-3 px-4 py-2 bg-amber-400 text-amber-900 text-sm font-medium shadow-md">
      <ShieldAlert size={16} className="shrink-0" />
      <span className="flex-1">
        Modo impersonation activo — viendo como{' '}
        <strong>{impersonatedBrokerName ?? 'broker'}</strong>.
        Los cambios que hagas afectarán a este broker.
      </span>
      <button
        onClick={handleExit}
        className="flex items-center gap-1.5 bg-amber-900/15 hover:bg-amber-900/25 px-3 py-1 rounded-lg transition-colors text-xs font-semibold"
      >
        <X size={12} />
        Salir
      </button>
    </div>
  )
}
