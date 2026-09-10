import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlarmClock, CheckCircle2, CircleDotDashed, Clock3, Gauge,
  ListTodo, Plus, TimerReset, TriangleAlert,
} from 'lucide-react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { LoadingSpinner } from '@/shared/components/common/LoadingSpinner'
import { EmptyState } from '@/shared/components/common/EmptyState'
import { ConfirmDialog } from '@/shared/components/common/ConfirmDialog'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { useAuthStore } from '@/features/auth'
import { useWebSocketEvent } from '@/shared/context/WebSocketContext'
import { getErrorMessage } from '@/shared/types/api'
import { cn } from '@/shared/lib/utils'
import { tasksService } from '../services/tasks.service'
import { TaskCard } from './TaskCard'
import { TaskFormDialog } from './TaskFormDialog'
import type { AgentOption, LeadTask, TaskMetrics, TaskStatus } from '../types'

const EMPTY_METRICS: TaskMetrics = {
  total: 0, pending: 0, in_progress: 0, overdue: 0, completed: 0,
  completion_rate: 0, on_time_rate: 0, avg_resolution_hours: null,
  avg_delay_hours: null, by_assignee: [],
}

const COLUMNS: Array<{
  status: TaskStatus
  title: string
  description: string
  icon: typeof ListTodo
  accent: string
}> = [
  { status: 'open', title: 'Pendientes', description: 'Próximas acciones', icon: ListTodo, accent: 'bg-slate-500' },
  { status: 'in_progress', title: 'En curso', description: 'Trabajo iniciado', icon: CircleDotDashed, accent: 'bg-blue-600' },
  { status: 'completed', title: 'Completadas', description: 'Seguimientos cerrados', icon: CheckCircle2, accent: 'bg-emerald-500' },
]

function hoursLabel(value: number | null) {
  if (value == null) return 'Sin datos'
  if (value < 24) return `${value.toLocaleString('es-CL')} h`
  return `${(value / 24).toLocaleString('es-CL', { maximumFractionDigits: 1 })} días`
}

export function TasksPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const highlightedTaskId = Number(searchParams.get('task')) || null
  const user = useAuthStore((state) => state.user)
  const { role } = usePermissions()
  const isBrokerAdmin = role === 'admin'
  const canCreateTask = role === 'admin' || role === 'agent'
  const [assignee, setAssignee] = useState('')
  const [agents, setAgents] = useState<AgentOption[]>([])
  const [tasks, setTasks] = useState<LeadTask[]>([])
  const [metrics, setMetrics] = useState<TaskMetrics>(EMPTY_METRICS)
  const [isLoading, setIsLoading] = useState(true)
  const [draggedTask, setDraggedTask] = useState<LeadTask | null>(null)
  const [movingTaskId, setMovingTaskId] = useState<number | null>(null)
  const [editTarget, setEditTarget] = useState<LeadTask | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<LeadTask | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [createDialogOpen, setCreateDialogOpen] = useState(false)

  const assignedTo = isBrokerAdmin && assignee ? Number(assignee) : undefined

  const fetchBoard = useCallback(async () => {
    setIsLoading(true)
    try {
      const base = { ...(assignedTo ? { assigned_to: assignedTo } : {}), limit: 200 }
      const [pending, inProgress, completed, summary] = await Promise.all([
        tasksService.getTasks({ ...base, status: 'open' }),
        tasksService.getTasks({ ...base, status: 'in_progress' }),
        tasksService.getTasks({ ...base, status: 'completed' }),
        tasksService.getMetrics(assignedTo),
      ])
      let next = [...pending.data, ...inProgress.data, ...completed.data]
      if (highlightedTaskId && !next.some((task) => task.id === highlightedTaskId)) {
        try {
          next = [await tasksService.getTask(highlightedTaskId), ...next]
        } catch {
          // It can be outside the currently selected executive.
        }
      }
      setTasks(next)
      setMetrics(summary)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }, [assignedTo, highlightedTaskId])

  useEffect(() => { fetchBoard() }, [fetchBoard])
  useEffect(() => {
    if (isBrokerAdmin) tasksService.listAgents().then(setAgents).catch(() => {})
  }, [isBrokerAdmin])
  useEffect(() => {
    if (highlightedTaskId && !isLoading) {
      document.getElementById(`task-${highlightedTaskId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [highlightedTaskId, isLoading])

  useWebSocketEvent(useCallback((event) => {
    if (event.type === 'lead_task_changed') fetchBoard()
  }, [fetchBoard]))

  const clearHighlight = useCallback(() => {
    const next = new URLSearchParams(searchParams)
    next.delete('task')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  const canMove = (task: LeadTask) => isBrokerAdmin || task.assigned_to === user?.id
  const canEdit = (task: LeadTask) => isBrokerAdmin || task.created_by === user?.id
  const columns = useMemo(() => Object.fromEntries(
    COLUMNS.map(({ status }) => [status, tasks
      .filter((task) => task.status === status)
      .sort((a, b) => new Date(a.due_at).getTime() - new Date(b.due_at).getTime())])
  ) as Record<TaskStatus, LeadTask[]>, [tasks])

  const moveTask = async (task: LeadTask, status: TaskStatus) => {
    if (!canMove(task) || task.status === status || movingTaskId) return
    setMovingTaskId(task.id)
    try {
      let updated: LeadTask
      if (status === 'completed') {
        updated = await tasksService.completeTask(task.id)
      } else if (status === 'in_progress') {
        if (task.status === 'completed') await tasksService.reopenTask(task.id)
        updated = await tasksService.startTask(task.id)
      } else {
        updated = await tasksService.reopenTask(task.id)
      }
      setTasks((current) => current.map((item) => item.id === updated.id ? updated : item))
      setMetrics(await tasksService.getMetrics(assignedTo))
      toast.success(status === 'completed' ? 'Tarea completada' : status === 'in_progress' ? 'Tarea iniciada' : 'Tarea movida a pendientes')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setMovingTaskId(null)
      setDraggedTask(null)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setIsDeleting(true)
    try {
      await tasksService.deleteTask(deleteTarget.id)
      setDeleteTarget(null)
      toast.success('Tarea eliminada')
      await fetchBoard()
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsDeleting(false)
    }
  }

  const metricCards = [
    { label: 'Pendientes', value: metrics.pending, icon: ListTodo, tone: 'text-slate-700 bg-slate-100' },
    { label: 'En curso', value: metrics.in_progress, icon: CircleDotDashed, tone: 'text-blue-700 bg-blue-50' },
    { label: 'Vencidas', value: metrics.overdue, icon: TriangleAlert, tone: 'text-rose-700 bg-rose-50' },
    { label: 'Cumplimiento', value: `${metrics.completion_rate}%`, icon: Gauge, tone: 'text-indigo-700 bg-indigo-50' },
    { label: 'A tiempo', value: `${metrics.on_time_rate}%`, icon: AlarmClock, tone: 'text-emerald-700 bg-emerald-50' },
    { label: 'Resolución prom.', value: hoursLabel(metrics.avg_resolution_hours), icon: TimerReset, tone: 'text-amber-700 bg-amber-50' },
  ]

  return (
    <div className="min-h-full bg-[linear-gradient(180deg,#F5F8FD_0%,#FFFFFF_320px)] p-4 sm:p-8">
      <div className="mx-auto max-w-[1500px]">
        <PageHeader
          title={isBrokerAdmin ? 'Tareas del equipo' : 'Mis tareas'}
          description={isBrokerAdmin ? 'Carga, avance y cumplimiento del seguimiento comercial.' : 'Organiza tus próximos contactos y mueve cada tarea a medida que avanzas.'}
          actions={canCreateTask && <Button size="sm" onClick={() => setCreateDialogOpen(true)}><Plus className="mr-1.5 h-4 w-4" /> Nueva tarea</Button>}
        />

        <div className="mb-5 grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
          {metricCards.map(({ label, value, icon: Icon, tone }) => (
            <div key={label} className="rounded-2xl border border-[#DFE7F2] bg-white p-3.5 shadow-[0_6px_22px_rgba(30,64,175,0.05)]">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">{label}</span>
                <span className={cn('rounded-lg p-1.5', tone)}><Icon className="h-3.5 w-3.5" /></span>
              </div>
              <p className="mt-2 text-xl font-bold tracking-tight text-slate-900">{isLoading ? '—' : value}</p>
            </div>
          ))}
        </div>

        <div className="mb-4 flex flex-col gap-3 rounded-2xl border border-[#DFE7F2] bg-white px-3.5 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2 text-xs text-slate-500"><Clock3 className="h-3.5 w-3.5" />Arrastra una tarjeta para cambiar su estado. Las vencidas se destacan en rojo.</div>
          {isBrokerAdmin && (
            <select value={assignee} onChange={(event) => { setAssignee(event.target.value); clearHighlight() }} aria-label="Filtrar por ejecutivo" className="h-9 rounded-lg border border-[#DCE5F2] bg-white px-3 text-xs font-medium text-[#475569] focus:outline-none focus:ring-2 focus:ring-[#1A56DB]">
              <option value="">Todos los ejecutivos</option>
              {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
            </select>
          )}
        </div>

        {highlightedTaskId && (
          <div className="mb-4 flex items-center justify-between rounded-xl border border-[#BFCFFF] bg-[#F3F6FF] px-3 py-2">
            <p className="text-xs font-medium text-[#1A56DB]">Tarea seleccionada desde un recordatorio</p>
            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={clearHighlight}>Quitar selección</Button>
          </div>
        )}

        {isLoading ? (
          <div className="flex justify-center rounded-2xl border border-[#DFE7F2] bg-white py-24"><LoadingSpinner size="lg" /></div>
        ) : (
          <div className="grid items-start gap-4 lg:grid-cols-3">
            {COLUMNS.map(({ status, title, description, icon: Icon, accent }) => (
              <section key={status} onDragOver={(event) => event.preventDefault()} onDrop={() => draggedTask && moveTask(draggedTask, status)} className={cn('min-h-[310px] rounded-2xl border border-[#DCE5F2] bg-[#F7F9FC] p-3 transition-colors', draggedTask && draggedTask.status !== status && 'border-dashed border-blue-300 bg-blue-50/40')}>
                <header className="mb-3 flex items-center justify-between px-1">
                  <div className="flex items-center gap-2.5"><span className={cn('h-8 w-1 rounded-full', accent)} /><div><h2 className="flex items-center gap-1.5 text-sm font-bold text-slate-800"><Icon className="h-4 w-4" />{title}</h2><p className="text-[11px] text-slate-500">{description}</p></div></div>
                  <span className="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-600 shadow-sm">{columns[status].length}</span>
                </header>
                {columns[status].length === 0 ? (
                  <div className="rounded-xl border border-dashed border-slate-200 bg-white/70"><EmptyState title={`Sin tareas ${title.toLowerCase()}`} description="Puedes soltar una tarea aquí." /></div>
                ) : (
                  <div className="space-y-2.5">
                    {columns[status].map((task) => (
                      <div key={task.id} draggable={canMove(task) && movingTaskId !== task.id} onDragStart={() => setDraggedTask(task)} onDragEnd={() => setDraggedTask(null)} className={cn('cursor-grab active:cursor-grabbing', movingTaskId === task.id && 'opacity-50')}>
                        <TaskCard task={task} highlighted={task.id === highlightedTaskId} showLead canComplete={canMove(task)} canEdit={canEdit(task)} canDelete={canEdit(task)} onStart={(item) => moveTask(item, 'in_progress')} onComplete={(item) => moveTask(item, 'completed')} onReopen={(item) => moveTask(item, 'open')} onEdit={setEditTarget} onDelete={setDeleteTarget} onOpenLead={(item) => navigate(`/leads?lead=${item.lead_id}`)} />
                      </div>
                    ))}
                  </div>
                )}
              </section>
            ))}
          </div>
        )}
      </div>

      {editTarget && <TaskFormDialog open onOpenChange={(open) => !open && setEditTarget(null)} leadId={editTarget.lead_id} leadName={editTarget.lead_name} defaultAssigneeId={editTarget.assigned_to} task={editTarget} onSaved={() => { setEditTarget(null); fetchBoard() }} />}
      {createDialogOpen && <TaskFormDialog open onOpenChange={setCreateDialogOpen} onSaved={() => { setCreateDialogOpen(false); fetchBoard() }} />}
      <ConfirmDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)} title="Eliminar tarea" description={`¿Eliminar “${deleteTarget?.title}”? Esta acción no se puede deshacer.`} confirmLabel="Eliminar" onConfirm={handleDelete} isLoading={isDeleting} />
    </div>
  )
}
