import { useState, useCallback, useEffect, useRef } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Menu } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { ImpersonationBanner } from './ImpersonationBanner'
import { useWebSocketEvent } from '@/shared/context/WebSocketContext'
import { useAuthStore } from '@/features/auth'
import { useDealsLive } from '@/features/deals/hooks/useDealsLive'
import { tasksService } from '@/features/tasks/services/tasks.service'

interface TaskReminderAlert {
  task_id: number
  lead_name?: string | null
  title: string
  due_at: string
}

function GlobalAlerts() {
  const navigate = useNavigate()
  const user = useAuthStore((state) => state.user)
  // Track which leads have already triggered a toast this session to avoid duplicates
  const notifiedRef = useRef(new Set<number>())
  const notifiedTasksRef = useRef(new Set<number>())
  const notifiedMetaMessagesRef = useRef(new Set<number>())

  const showTaskReminder = useCallback((reminder: TaskReminderAlert) => {
    if (notifiedTasksRef.current.has(reminder.task_id)) return
    notifiedTasksRef.current.add(reminder.task_id)

    const due = new Intl.DateTimeFormat('es-CL', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(reminder.due_at))
    toast.info(`Recordatorio: ${reminder.title}`, {
      description: `${reminder.lead_name || 'Lead'} · vence ${due}`,
      duration: 12000,
      action: {
        label: 'Ver tarea',
        onClick: () => navigate(`/tasks?task=${reminder.task_id}`),
      },
    })

    // The server retries until this confirmation is persisted. If it fails,
    // remove the local dedup entry so a later retry can be shown again.
    tasksService.acknowledgeReminder(reminder.task_id).catch(() => {
      notifiedTasksRef.current.delete(reminder.task_id)
    })
  }, [navigate])

  useEffect(() => {
    if (user?.role !== 'agent' || !user.broker_id) return
    tasksService.getPendingReminders()
      .then((tasks) => tasks.forEach((task) => showTaskReminder({
        task_id: task.id,
        lead_name: task.lead_name,
        title: task.title,
        due_at: task.due_at,
      })))
      .catch(() => {})
  }, [showTaskReminder, user?.broker_id, user?.id, user?.role])

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
    if (event.type === 'lead_task_reminder') {
      showTaskReminder(event.data as TaskReminderAlert)
    }
    if (event.type === 'meta_message_received') {
      const d = event.data as {
        message_id: number
        conversation_id: number
        channel: string
        assigned_to?: number | null
      }
      if (user?.role === 'agent' && d.assigned_to !== user.id) return
      if (notifiedMetaMessagesRef.current.has(d.message_id)) return
      notifiedMetaMessagesRef.current.add(d.message_id)
      const channel = d.channel === 'facebook' ? 'Messenger' : d.channel === 'instagram' ? 'Instagram' : 'WhatsApp'
      toast.info(`Nuevo mensaje por ${channel}`, {
        description: 'Hay una conversación que requiere atención.',
        duration: 9000,
        action: {
          label: 'Abrir conversación',
          onClick: () => navigate(`/meta-inbox?conversation=${d.conversation_id}`),
        },
      })
    }
    if (event.type === 'meta_assignment_conflict' && user?.role === 'admin') {
      const d = event.data as { conversation_id?: number; lead_id: number }
      toast.warning('Conflicto de asignación Meta', {
        description: 'El dueño del canal y el ejecutivo del lead no coinciden. El envío quedó bloqueado.',
        duration: 12000,
        action: {
          label: 'Resolver',
          onClick: () => navigate(d.conversation_id ? `/meta-inbox?conversation=${d.conversation_id}` : '/meta-inbox?conflicts=1'),
        },
      })
    }
    if (event.type === 'meta_ai_handoff_required') {
      const d = event.data as { conversation_id: number; assigned_to?: number | null; reason?: string }
      if (user?.role === 'agent' && d.assigned_to !== user.id) return
      toast.warning('Sofía solicita revisión humana', {
        description: 'La respuesta automática fue bloqueada por una regla de seguridad.',
        duration: 12000,
        action: { label: 'Revisar conversación', onClick: () => navigate(`/meta-inbox?conversation=${d.conversation_id}`) },
      })
    }
    if (event.type === 'meta_connection_expiring') {
      const d = event.data as { connection_id: number; owner_user_id?: number | null; expires_at?: string | null }
      if (user?.role === 'agent' && d.owner_user_id !== user.id) return
      toast.warning('Una conexión Meta está por vencer', {
        description: d.expires_at ? `Vence el ${new Date(d.expires_at).toLocaleDateString('es-CL')}.` : 'Vuelve a autorizarla para evitar interrupciones.',
        duration: 12000,
        action: { label: 'Revisar canales', onClick: () => navigate('/my-channels') },
      })
    }
    if (event.type.startsWith('meta_ad_campaign_')) {
      const d = event.data as { campaign_id: number; status?: string }
      if (event.type === 'meta_ad_campaign_submitted' && user?.role !== 'admin') return
      const labels: Record<string, { title: string; description: string; tone: 'success' | 'warning' | 'error' | 'info' }> = {
        meta_ad_campaign_submitted: { title: 'Campaña pendiente de revisión', description: 'Un ejecutivo envió un borrador a jefatura.', tone: 'info' },
        meta_ad_campaign_approved: { title: 'Campaña aprobada', description: 'Está lista para publicarse pausada en Meta.', tone: 'success' },
        meta_ad_campaign_rejected: { title: 'Campaña devuelta', description: 'Revisa el comentario de jefatura antes de reenviarla.', tone: 'warning' },
        meta_ad_campaign_published: { title: 'Campaña publicada en pausa', description: 'Todavía no consume presupuesto.', tone: 'success' },
        meta_ad_campaign_activated: { title: 'Campaña Meta activada', description: 'La campaña comenzó a consumir presupuesto.', tone: 'warning' },
        meta_ad_campaign_paused: { title: 'Campaña Meta pausada', description: 'El gasto fue detenido.', tone: 'info' },
        meta_ad_campaign_error: { title: 'Error parcial al publicar', description: 'Los objetos creados permanecen pausados. Revisa el detalle.', tone: 'error' },
      }
      const alert = labels[event.type]
      if (!alert) return
      toast[alert.tone](alert.title, {
        description: alert.description,
        duration: 10000,
        action: { label: 'Ver campaña', onClick: () => navigate(`/meta-ads?campaign=${d.campaign_id}`) },
      })
    }
  }, [navigate, showTaskReminder, user?.id, user?.role]))

  return null
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const user = useAuthStore((s) => s.user)
  useDealsLive(user?.broker_id ?? undefined)

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
