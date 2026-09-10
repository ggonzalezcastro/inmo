import {
  Bell,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Pencil,
  RotateCcw,
  Trash2,
  UserRound,
} from 'lucide-react'
import { Button } from '@/shared/components/ui/button'
import { cn, formatDateTime } from '@/shared/lib/utils'
import type { LeadTask } from '../types'

interface TaskCardProps {
  task: LeadTask
  highlighted?: boolean
  showLead?: boolean
  canComplete?: boolean
  canEdit?: boolean
  canDelete?: boolean
  onComplete?: (task: LeadTask) => void
  onStart?: (task: LeadTask) => void
  onReopen?: (task: LeadTask) => void
  onEdit?: (task: LeadTask) => void
  onDelete?: (task: LeadTask) => void
  onOpenLead?: (task: LeadTask) => void
}

function reminderLabel(minutes: LeadTask['reminder_minutes_before']) {
  if (minutes == null) return 'Sin aviso'
  if (minutes === 0) return 'Al vencer'
  if (minutes === 15) return '15 min antes'
  if (minutes === 60) return '1 hora antes'
  return '1 día antes'
}

export function TaskCard({
  task,
  highlighted = false,
  showLead = false,
  canComplete = false,
  canEdit = false,
  canDelete = false,
  onComplete,
  onStart,
  onReopen,
  onEdit,
  onDelete,
  onOpenLead,
}: TaskCardProps) {
  const completed = task.status === 'completed'
  const dueTime = new Date(task.due_at).getTime()
  const diff = dueTime - Date.now()
  const overdue = !completed && diff < 0
  const dueSoon = !completed && !overdue && diff <= 24 * 60 * 60 * 1000

  return (
    <article
      id={`task-${task.id}`}
      className={cn(
        'group rounded-xl border bg-white p-3.5 shadow-sm transition-all duration-200',
        completed && 'bg-[#F8FAFC] opacity-75',
        overdue && 'border-rose-200 shadow-[0_8px_24px_rgba(225,29,72,0.07)]',
        dueSoon && 'border-amber-200',
        !completed && !overdue && !dueSoon && 'border-[#DCE5F2] hover:border-[#BFCFFF]',
        highlighted && 'ring-2 ring-[#1A56DB] ring-offset-2'
      )}
    >
      <div className="flex items-start gap-3">
        <button
          type="button"
          disabled={!canComplete}
          onClick={() => completed ? onReopen?.(task) : onComplete?.(task)}
          className={cn(
            'mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border transition-colors',
            completed
              ? 'border-emerald-300 bg-emerald-50 text-emerald-600'
              : 'border-[#C8D4E3] text-transparent hover:border-[#1A56DB] hover:text-[#1A56DB]',
            !canComplete && 'cursor-default'
          )}
          aria-label={completed ? 'Reabrir tarea' : 'Completar tarea'}
          title={completed ? 'Reabrir tarea' : 'Completar tarea'}
        >
          <CheckCircle2 className="h-4 w-4" />
        </button>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className={cn('text-sm font-semibold leading-5 text-foreground', completed && 'line-through')}>
                {task.title}
              </h3>
              {showLead && (
                <button
                  type="button"
                  onClick={() => onOpenLead?.(task)}
                  className="mt-0.5 inline-flex max-w-full items-center gap-1 text-xs font-medium text-[#1A56DB] hover:underline"
                >
                  <span className="truncate">{task.lead_name || task.lead_phone || `Lead #${task.lead_id}`}</span>
                  <ExternalLink className="h-3 w-3 shrink-0" />
                </button>
              )}
            </div>

            {(canEdit || canDelete || canComplete) && (
              <div className="flex shrink-0 items-center gap-0.5 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
                {task.status === 'open' && canComplete && onStart && (
                  <Button variant="ghost" size="sm" className="h-7 px-2 text-[10px] text-[#1A56DB]" onClick={() => onStart(task)} title="Mover a En curso">
                    Iniciar
                  </Button>
                )}
                {completed && canComplete && (
                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onReopen?.(task)} title="Reabrir">
                    <RotateCcw className="h-3.5 w-3.5" />
                  </Button>
                )}
                {canEdit && (
                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => onEdit?.(task)} title="Editar">
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                )}
                {canDelete && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-muted-foreground hover:text-destructive"
                    onClick={() => onDelete?.(task)}
                    title="Eliminar"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            )}
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[11px] text-muted-foreground">
            <span
              className={cn(
                'inline-flex items-center gap-1 font-medium',
                overdue && 'text-rose-600',
                dueSoon && 'text-amber-700',
                completed && 'text-slate-500'
              )}
            >
              <Clock3 className="h-3 w-3" />
              {overdue ? 'Vencida · ' : dueSoon ? 'Próxima · ' : ''}{formatDateTime(task.due_at)}
            </span>
            <span className="inline-flex items-center gap-1">
              <UserRound className="h-3 w-3" />
              {task.assignee_name || 'Sin responsable'}
            </span>
            <span className="inline-flex items-center gap-1">
              <Bell className="h-3 w-3" />
              {reminderLabel(task.reminder_minutes_before)}
            </span>
          </div>
        </div>
      </div>
    </article>
  )
}
