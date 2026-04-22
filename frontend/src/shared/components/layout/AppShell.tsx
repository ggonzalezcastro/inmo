import { useState, useCallback, useRef } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Menu } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { ImpersonationBanner } from './ImpersonationBanner'
import { useWebSocketEvent } from '@/shared/context/WebSocketContext'
import { useAuthStore } from '@/features/auth'
import { useDealsLive } from '@/features/deals/hooks/useDealsLive'

function GlobalAlerts() {
  const navigate = useNavigate()
  // Track which leads have already triggered a toast this session to avoid duplicates
  const notifiedRef = useRef(new Set<number>())

  useWebSocketEvent(useCallback((event) => {
    if (event.type === 'lead_frustrated') {
      const d = event.data as { lead_name: string; lead_id: number; last_message: string }
      if (notifiedRef.current.has(d.lead_id)) return
      notifiedRef.current.add(d.lead_id)

      const name = d.lead_name || `Lead #${d.lead_id}`
      toast.warning(`🚨 ${name} está frustrado`, {
        description: d.last_message
          ? `"${d.last_message.slice(0, 90)}…"`
          : 'Requiere atención inmediata',
        duration: 10000,
        action: {
          label: 'Ver conversación',
          onClick: () => {
            notifiedRef.current.delete(d.lead_id) // Allow re-alert if manually dismissed
            navigate(`/conversations?lead=${d.lead_id}`)
          },
        },
      })
    }
    // When a lead is de-escalated (AI re-enabled), reset the dedup entry so a
    // future re-escalation will show a new toast.
    if (event.type === 'human_mode_changed') {
      const d = event.data as { lead_id: number; human_mode: boolean }
      if (!d.human_mode) {
        notifiedRef.current.delete(d.lead_id)
      }
    }
  }, [navigate]))

  return null
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const user = useAuthStore((s) => s.user)
  useDealsLive(user?.broker_id)

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <GlobalAlerts />
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar — hidden on mobile unless mobileOpen */}
      <div
        className={`
          fixed inset-y-0 left-0 z-40 transition-transform duration-200
          lg:static lg:translate-x-0 lg:z-auto
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed((v) => !v)}
          onMobileClose={() => setMobileOpen(false)}
        />
      </div>

      <main className="flex-1 overflow-y-auto min-w-0 flex flex-col">
        <ImpersonationBanner />
        {/* Mobile top bar */}
        <div className="sticky top-0 z-20 flex items-center gap-3 px-4 py-3 bg-background border-b border-border lg:hidden">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-1.5 rounded-lg text-muted-foreground hover:bg-accent transition-colors"
            aria-label="Abrir menú"
          >
            <Menu size={20} />
          </button>
          <span className="text-sm font-semibold text-foreground">Captame.cl</span>
        </div>

        <div className="flex-1">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
