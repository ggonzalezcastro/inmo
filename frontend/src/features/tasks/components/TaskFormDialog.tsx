import { useEffect, useMemo, useState } from 'react'
import { CalendarClock, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { getErrorMessage } from '@/shared/types/api'
import { usePermissions } from '@/shared/hooks/usePermissions'
import {
  LeadSearchCombobox,
  type LeadOption,
} from '@/features/appointments/components/LeadSearchCombobox'
import { tasksService } from '../services/tasks.service'
import type { AgentOption, LeadTask, ReminderOffset } from '../types'

interface TaskFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  leadId?: number | null
  leadName?: string | null
  defaultAssigneeId?: number | null
  task?: LeadTask | null
  onSaved: (task: LeadTask) => void
}

function toLocalInput(iso?: string | null) {
  const date = iso ? new Date(iso) : new Date(Date.now() + 60 * 60 * 1000)
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

export function TaskFormDialog({
  open,
  onOpenChange,
  leadId,
  leadName,
  defaultAssigneeId,
  task,
  onSaved,
}: TaskFormDialogProps) {
  const { role } = usePermissions()
  const isBrokerAdmin = role === 'admin'
  const [title, setTitle] = useState('')
  const [dueAt, setDueAt] = useState(toLocalInput())
  const [reminder, setReminder] = useState<string>('60')
  const [assigneeId, setAssigneeId] = useState('')
  const [agents, setAgents] = useState<AgentOption[]>([])
  const [selectedLead, setSelectedLead] = useState<LeadOption | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  const isEditing = !!task
  const resolvedLeadId = leadId ?? task?.lead_id ?? selectedLead?.id ?? null
  const resolvedLeadName = leadName ?? task?.lead_name ?? selectedLead?.name ?? null
  const requiresLeadSelection = !isEditing && !leadId

  useEffect(() => {
    if (!open) return
    setTitle(task?.title ?? '')
    setDueAt(toLocalInput(task?.due_at))
    setReminder(task?.reminder_minutes_before == null ? 'none' : String(task.reminder_minutes_before))
    setAssigneeId(String(task?.assigned_to ?? defaultAssigneeId ?? ''))
    if (!leadId) setSelectedLead(null)
  }, [open, task, defaultAssigneeId, leadId])

  useEffect(() => {
    if (!open || !isBrokerAdmin) return
    tasksService.listAgents().then(setAgents).catch(() => {
      toast.error('No se pudieron cargar los ejecutivos')
    })
  }, [open, isBrokerAdmin])

  const selectedAgentMissing = useMemo(
    () => assigneeId && agents.length > 0 && !agents.some((agent) => String(agent.id) === assigneeId),
    [agents, assigneeId]
  )

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!title.trim() || !dueAt) return
    if (!resolvedLeadId) {
      toast.error('Selecciona el lead asociado a la tarea')
      return
    }
    if (isBrokerAdmin && !assigneeId) {
      toast.error('Selecciona un ejecutivo responsable')
      return
    }

    setIsSaving(true)
    try {
      const reminderValue: ReminderOffset = reminder === 'none'
        ? null
        : Number(reminder) as Exclude<ReminderOffset, null>
      const common = {
        title: title.trim(),
        due_at: new Date(dueAt).toISOString(),
        reminder_minutes_before: reminderValue,
        ...(isBrokerAdmin ? { assigned_to: assigneeId ? Number(assigneeId) : null } : {}),
      }
      const saved = isEditing
        ? await tasksService.updateTask(task.id, common)
        : await tasksService.createTask(resolvedLeadId, common)
      toast.success(isEditing ? 'Tarea actualizada' : 'Tarea creada')
      onSaved(saved)
      onOpenChange(false)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-[#EBF2FF] text-[#1A56DB]">
            <CalendarClock className="h-5 w-5" />
          </div>
          <DialogTitle>{isEditing ? 'Editar tarea' : 'Nueva tarea'}</DialogTitle>
          <DialogDescription>
            {resolvedLeadName
              ? `Seguimiento para ${resolvedLeadName}`
              : 'Selecciona un lead y programa el próximo contacto.'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {requiresLeadSelection && (
            <div className="space-y-1.5">
              <Label>Lead</Label>
              <LeadSearchCombobox
                value={selectedLead}
                onChange={(lead) => {
                  setSelectedLead(lead)
                  if (isBrokerAdmin) setAssigneeId(String(lead?.assigned_to ?? ''))
                }}
                placeholder="Buscar por nombre, teléfono o email…"
              />
              <p className="text-[11px] text-muted-foreground">
                La tarea quedará vinculada al historial de este lead.
              </p>
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="task-title">Tarea</Label>
            <Input
              id="task-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={200}
              placeholder="Ej. Llamar para confirmar documentación"
              autoFocus
            />
          </div>

          {isBrokerAdmin && (
            <div className="space-y-1.5">
              <Label htmlFor="task-assignee">Responsable</Label>
              <select
                id="task-assignee"
                value={assigneeId}
                onChange={(event) => setAssigneeId(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="">Seleccionar ejecutivo…</option>
                {selectedAgentMissing && task?.assignee_name && (
                  <option value={assigneeId}>{task.assignee_name}</option>
                )}
                {agents.map((agent) => (
                  <option key={agent.id} value={agent.id}>{agent.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="task-due">Fecha y hora</Label>
              <Input
                id="task-due"
                type="datetime-local"
                value={dueAt}
                onChange={(event) => setDueAt(event.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="task-reminder">Recordatorio</Label>
              <select
                id="task-reminder"
                value={reminder}
                onChange={(event) => setReminder(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="none">Sin aviso</option>
                <option value="0">Al vencer</option>
                <option value="15">15 min antes</option>
                <option value="60">1 hora antes</option>
                <option value="1440">1 día antes</option>
              </select>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSaving || !resolvedLeadId || !title.trim() || !dueAt}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? 'Guardar cambios' : 'Crear tarea'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
