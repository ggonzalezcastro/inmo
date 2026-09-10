import { useCallback, useEffect, useMemo, useState } from 'react'
import { FileText, Handshake, ListTodo, Loader2, Plus, Send } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { Textarea } from '@/shared/components/ui/textarea'
import { ConfirmDialog } from '@/shared/components/common/ConfirmDialog'
import { LoadingSpinner } from '@/shared/components/common/LoadingSpinner'
import { useAuthStore } from '@/features/auth'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { useWebSocketEvent } from '@/shared/context/WebSocketContext'
import { formatDateTime } from '@/shared/lib/utils'
import { getErrorMessage } from '@/shared/types/api'
import {
  TaskCard,
  AdvisoryFormDialog,
  TaskFormDialog,
  tasksService,
  type AdvisoryChannel,
  type LeadAdvisory,
  type LeadNote,
  type LeadTask,
} from '@/features/tasks'
import type { Lead } from '../types'

interface LeadFollowUpPanelProps {
  lead: Lead
  readOnly?: boolean
  openTaskOnMount?: boolean
  onTaskDialogOpened?: () => void
}

const NOTES_LIMIT = 50

const ADVISORY_CHANNEL_LABELS: Record<AdvisoryChannel, string> = {
  whatsapp: 'WhatsApp',
  phone: 'Llamada',
  video_call: 'Videollamada',
  property_visit: 'Visita a propiedad',
  in_person: 'Reunión presencial',
  other: 'Otro canal',
}

export function LeadFollowUpPanel({
  lead,
  readOnly = false,
  openTaskOnMount = false,
  onTaskDialogOpened,
}: LeadFollowUpPanelProps) {
  const user = useAuthStore((state) => state.user)
  const { role } = usePermissions()
  const isBrokerAdmin = role === 'admin'
  const [notes, setNotes] = useState<LeadNote[]>([])
  const [advisories, setAdvisories] = useState<LeadAdvisory[]>([])
  const [notesTotal, setNotesTotal] = useState(0)
  const [tasks, setTasks] = useState<LeadTask[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isLoadingMoreNotes, setIsLoadingMoreNotes] = useState(false)
  const [noteBody, setNoteBody] = useState('')
  const [isSavingNote, setIsSavingNote] = useState(false)
  const [taskDialogOpen, setTaskDialogOpen] = useState(false)
  const [advisoryDialogOpen, setAdvisoryDialogOpen] = useState(false)
  const [editTarget, setEditTarget] = useState<LeadTask | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<LeadTask | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    if (!openTaskOnMount || readOnly) return
    setTaskDialogOpen(true)
    onTaskDialogOpened?.()
  }, [onTaskDialogOpened, openTaskOnMount, readOnly])

  const fetchFollowUp = useCallback(async () => {
    setIsLoading(true)
    try {
      const [advisoriesResult, notesResult, tasksResult] = await Promise.all([
        tasksService.getAdvisories(lead.id),
        tasksService.getNotes(lead.id, 0, NOTES_LIMIT),
        tasksService.getLeadTasks(lead.id),
      ])
      setAdvisories(advisoriesResult.data)
      setNotes(notesResult.data)
      setNotesTotal(notesResult.total)
      setTasks(tasksResult.data)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }, [lead.id])

  useEffect(() => { fetchFollowUp() }, [fetchFollowUp])

  const fetchTasks = useCallback(async () => {
    try {
      const result = await tasksService.getLeadTasks(lead.id)
      setTasks(result.data)
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }, [lead.id])

  useWebSocketEvent(useCallback((event) => {
    const data = event.data as { lead_id?: number }
    if (data.lead_id !== lead.id) return
    if (event.type === 'lead_task_changed') fetchTasks()
    if (event.type === 'lead_advisory_created') {
      tasksService.getAdvisories(lead.id).then((result) => setAdvisories(result.data)).catch(() => {})
    }
  }, [fetchTasks, lead.id]))

  const sortedTasks = useMemo(() => [...tasks].sort((a, b) => {
    if (a.status !== b.status) return a.status === 'open' ? -1 : 1
    return new Date(a.due_at).getTime() - new Date(b.due_at).getTime()
  }), [tasks])

  const createNote = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!noteBody.trim()) return
    setIsSavingNote(true)
    try {
      const created = await tasksService.createNote(lead.id, noteBody.trim())
      setNotes((current) => [created, ...current])
      setNotesTotal((current) => current + 1)
      setNoteBody('')
      toast.success('Nota agregada')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsSavingNote(false)
    }
  }

  const loadMoreNotes = async () => {
    setIsLoadingMoreNotes(true)
    try {
      const result = await tasksService.getNotes(lead.id, notes.length, NOTES_LIMIT)
      setNotes((current) => {
        const existingIds = new Set(current.map((note) => note.id))
        return [...current, ...result.data.filter((note) => !existingIds.has(note.id))]
      })
      setNotesTotal(result.total)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoadingMoreNotes(false)
    }
  }

  const canComplete = (task: LeadTask) => !readOnly && (isBrokerAdmin || task.assigned_to === user?.id)
  const canEdit = (task: LeadTask) => !readOnly && (isBrokerAdmin || task.created_by === user?.id)

  const changeStatus = async (task: LeadTask, complete: boolean) => {
    try {
      const updated = complete
        ? await tasksService.completeTask(task.id)
        : await tasksService.reopenTask(task.id)
      setTasks((current) => current.map((item) => item.id === updated.id ? updated : item))
      toast.success(complete ? 'Tarea completada' : 'Tarea reabierta')
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setIsDeleting(true)
    try {
      await tasksService.deleteTask(deleteTarget.id)
      setTasks((current) => current.filter((task) => task.id !== deleteTarget.id))
      setDeleteTarget(null)
      toast.success('Tarea eliminada')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsDeleting(false)
    }
  }

  if (isLoading) {
    return <div className="flex justify-center py-16"><LoadingSpinner /></div>
  }

  return (
    <div className="space-y-5 pb-3">
      <section>
        <div className="mb-2.5 flex items-center justify-between">
          <div>
            <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#334155]">
              <Handshake className="h-3.5 w-3.5 text-emerald-600" /> Asesorías comerciales
            </h4>
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              {advisories.length === 0
                ? 'Aún no hay asesorías verificadas'
                : `${advisories.length} ${advisories.length === 1 ? 'interacción registrada' : 'interacciones registradas'}`}
            </p>
          </div>
          {!readOnly && (
            <Button
              size="sm"
              variant="outline"
              className="h-8 border-emerald-200 text-xs text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800"
              onClick={() => setAdvisoryDialogOpen(true)}
            >
              <Plus className="mr-1 h-3.5 w-3.5" /> Registrar
            </Button>
          )}
        </div>

        {advisories.length === 0 ? (
          <div className="rounded-xl border border-dashed border-emerald-200 bg-emerald-50/40 px-4 py-6 text-center">
            <Handshake className="mx-auto mb-2 h-5 w-5 text-emerald-500" />
            <p className="text-xs font-medium text-emerald-800">Lead aún no asesorado</p>
            <p className="mt-1 text-[11px] text-emerald-700/75">
              Registra la primera conversación, llamada o reunión comercial efectiva.
            </p>
          </div>
        ) : (
          <ol className="space-y-2">
            {advisories.map((advisory) => (
              <li key={advisory.id} className="rounded-xl border border-emerald-100 bg-emerald-50/35 px-3 py-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-emerald-800">
                    {ADVISORY_CHANNEL_LABELS[advisory.channel]}
                  </span>
                  <span className="text-[10px] text-emerald-700/70">
                    {formatDateTime(advisory.occurred_at)}
                  </span>
                </div>
                <p className="mt-0.5 text-[11px] text-[#475569]">
                  {advisory.advisor_name || 'Ejecutivo no disponible'}
                </p>
                {advisory.notes && (
                  <p className="mt-1.5 whitespace-pre-wrap break-words text-xs leading-4 text-[#334155]">
                    {advisory.notes}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>

      <div className="h-px bg-border" />

      <section>
        <div className="mb-2.5 flex items-center justify-between">
          <div>
            <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#334155]">
              <ListTodo className="h-3.5 w-3.5 text-[#1A56DB]" /> Tareas
            </h4>
            <p className="mt-0.5 text-[11px] text-muted-foreground">
              {tasks.filter((task) => task.status === 'open').length} pendientes
            </p>
          </div>
          {!readOnly && (
            <Button size="sm" className="h-8 text-xs" onClick={() => setTaskDialogOpen(true)}>
              <Plus className="mr-1 h-3.5 w-3.5" /> Nueva tarea
            </Button>
          )}
        </div>

        {sortedTasks.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[#C8D4E3] bg-[#F8FAFC] px-4 py-7 text-center">
            <ListTodo className="mx-auto mb-2 h-5 w-5 text-[#94A3B8]" />
            <p className="text-xs font-medium text-[#475569]">Sin tareas de seguimiento</p>
            <p className="mt-1 text-[11px] text-muted-foreground">Programa el próximo contacto con este lead.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {sortedTasks.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                canComplete={canComplete(task)}
                canEdit={canEdit(task)}
                canDelete={canEdit(task)}
                onComplete={(item) => changeStatus(item, true)}
                onReopen={(item) => changeStatus(item, false)}
                onEdit={setEditTarget}
                onDelete={setDeleteTarget}
              />
            ))}
          </div>
        )}
      </section>

      <div className="h-px bg-border" />

      <section>
        <div className="mb-2.5">
          <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#334155]">
            <FileText className="h-3.5 w-3.5 text-[#1A56DB]" /> Notas internas
          </h4>
          <p className="mt-0.5 text-[11px] text-muted-foreground">Historial privado del equipo comercial</p>
        </div>

        {!readOnly && (
          <form onSubmit={createNote} className="mb-3 rounded-xl border border-[#DCE5F2] bg-[#F8FAFD] p-2.5">
            <Textarea
              value={noteBody}
              onChange={(event) => setNoteBody(event.target.value)}
              maxLength={5000}
              rows={3}
              placeholder="Escribe una observación relevante para el equipo…"
              className="min-h-[76px] resize-none border-0 bg-transparent p-1 shadow-none focus-visible:ring-0"
            />
            <div className="mt-1 flex items-center justify-between border-t border-[#E2EAF4] pt-2">
              <span className="text-[10px] text-muted-foreground">Solo visible dentro del CRM</span>
              <Button type="submit" size="sm" className="h-7 px-2.5 text-xs" disabled={!noteBody.trim() || isSavingNote}>
                {isSavingNote ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Send className="mr-1 h-3.5 w-3.5" />}
                Agregar
              </Button>
            </div>
          </form>
        )}

        {notes.length === 0 ? (
          <p className="rounded-xl border border-dashed border-[#C8D4E3] py-6 text-center text-xs text-muted-foreground">
            Aún no hay notas internas.
          </p>
        ) : (
          <>
            <ol className="relative ml-2 border-l border-[#DCE5F2] pl-4">
              {notes.map((note) => (
                <li key={note.id} className="relative pb-4 last:pb-0">
                  <span className="absolute -left-[20px] top-1.5 h-2 w-2 rounded-full border-2 border-white bg-[#1A56DB] ring-1 ring-[#BFCFFF]" />
                  <p className="whitespace-pre-wrap break-words text-sm leading-5 text-[#334155]">{note.body}</p>
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    {note.author_name || 'Nota migrada'} · {formatDateTime(note.created_at)}
                  </p>
                </li>
              ))}
            </ol>
            {notes.length < notesTotal && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-3 h-8 w-full text-xs"
                disabled={isLoadingMoreNotes}
                onClick={loadMoreNotes}
              >
                {isLoadingMoreNotes && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                Cargar notas anteriores ({notesTotal - notes.length})
              </Button>
            )}
          </>
        )}
      </section>

      <TaskFormDialog
        open={taskDialogOpen || !!editTarget}
        onOpenChange={(open) => {
          if (!open) {
            setTaskDialogOpen(false)
            setEditTarget(null)
          }
        }}
        leadId={lead.id}
        leadName={lead.name}
        defaultAssigneeId={lead.assigned_to}
        task={editTarget}
        onSaved={(saved) => {
          setTasks((current) => {
            const exists = current.some((task) => task.id === saved.id)
            return exists
              ? current.map((task) => task.id === saved.id ? saved : task)
              : [...current, saved]
          })
          setTaskDialogOpen(false)
          setEditTarget(null)
        }}
      />

      <AdvisoryFormDialog
        open={advisoryDialogOpen}
        onOpenChange={setAdvisoryDialogOpen}
        leadId={lead.id}
        leadName={lead.name}
        defaultAdvisorId={lead.assigned_to}
        onSaved={(saved) => {
          setAdvisories((current) => current.some((item) => item.id === saved.id)
            ? current
            : [saved, ...current])
          setAdvisoryDialogOpen(false)
        }}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Eliminar tarea"
        description={`¿Eliminar “${deleteTarget?.title}”? Esta acción no se puede deshacer.`}
        confirmLabel="Eliminar"
        onConfirm={handleDelete}
        isLoading={isDeleting}
      />
    </div>
  )
}
