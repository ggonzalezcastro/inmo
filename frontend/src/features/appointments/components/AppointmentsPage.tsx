import { useState, useEffect } from 'react'
import { Plus, Check, X, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { type ColumnDef } from '@tanstack/react-table'
import { Button } from '@/shared/components/ui/button'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { DataTable } from '@/shared/components/common/DataTable'
import { ConfirmDialog } from '@/shared/components/common/ConfirmDialog'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/shared/components/ui/dialog'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { Textarea } from '@/shared/components/ui/textarea'
import { cn, formatDateTime } from '@/shared/lib/utils'
import { APPOINTMENT_STATUS_CONFIG } from '@/shared/lib/constants'
import { getErrorMessage } from '@/shared/types/api'
import {
  appointmentsService,
  type Appointment,
  type AppointmentStatus,
} from '../services/appointments.service'

function StatusBadge({ status }: { status: AppointmentStatus }) {
  const config = APPOINTMENT_STATUS_CONFIG[status] ?? {
    label: status,
    className: 'bg-slate-100 text-slate-600 border-slate-200',
  }
  return (
    <span className={cn('inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium', config.className)}>
      {config.label}
    </span>
  )
}

export function AppointmentsPage() {
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [cancelTarget, setCancelTarget] = useState<Appointment | null>(null)
  const [actionLoading, setActionLoading] = useState<number | null>(null)

  const [newLeadId, setNewLeadId] = useState('')
  const [newDate, setNewDate] = useState('')
  const [newNotes, setNewNotes] = useState('')
  const [creating, setCreating] = useState(false)

  const load = async () => {
    setIsLoading(true)
    try {
      const data = await appointmentsService.getAll()
      setAppointments(Array.isArray(data) ? data : [])
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleConfirm = async (id: number) => {
    setActionLoading(id)
    try {
      const updated = await appointmentsService.confirm(id)
      setAppointments((prev) => prev.map((a) => (a.id === id ? updated : a)))
      toast.success('Cita confirmada')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setActionLoading(null)
    }
  }

  const handleCancel = async () => {
    if (!cancelTarget) return
    setActionLoading(cancelTarget.id)
    try {
      const updated = await appointmentsService.cancel(cancelTarget.id)
      setAppointments((prev) => prev.map((a) => (a.id === cancelTarget.id ? updated : a)))
      toast.success('Cita cancelada')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setActionLoading(null)
      setCancelTarget(null)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      const appt = await appointmentsService.create({
        lead_id: parseInt(newLeadId),
        scheduled_at: newDate,
        notes: newNotes || undefined,
      })
      setAppointments((prev) => [appt, ...prev])
      toast.success('Cita creada')
      setShowCreate(false)
      setNewLeadId('')
      setNewDate('')
      setNewNotes('')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setCreating(false)
    }
  }

  const columns: ColumnDef<Appointment>[] = [
    {
      accessorKey: 'lead_name',
      header: 'Lead',
      cell: ({ row }) => (
        <span className="font-medium">{row.original.lead_name ?? `Lead #${row.original.lead_id}`}</span>
      ),
    },
    {
      accessorKey: 'scheduled_at',
      header: 'Fecha y hora',
      cell: ({ row }) => formatDateTime(row.original.scheduled_at),
    },
    {
      accessorKey: 'status',
      header: 'Estado',
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
    {
      accessorKey: 'meeting_link',
      header: 'Enlace',
      cell: ({ row }) =>
        row.original.meeting_link ? (
          <a
            href={row.original.meeting_link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary text-xs hover:underline"
          >
            Abrir meet
          </a>
        ) : (
          <span className="text-muted-foreground text-xs">—</span>
        ),
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => {
        const a = row.original
        const loading = actionLoading === a.id
        return (
          <div className="flex items-center gap-1">
            {a.status === 'scheduled' && (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs text-emerald-600 border-emerald-200 hover:bg-emerald-50"
                  onClick={() => handleConfirm(a.id)}
                  disabled={loading}
                >
                  {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3 mr-1" />}
                  Confirmar
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs text-rose-600 border-rose-200 hover:bg-rose-50"
                  onClick={() => setCancelTarget(a)}
                  disabled={loading}
                >
                  <X className="h-3 w-3 mr-1" />
                  Cancelar
                </Button>
              </>
            )}
          </div>
        )
      },
    },
  ]

  return (
    <div className="p-8 space-y-6">
      <PageHeader
        title="Citas"
        description="Gestión de visitas y reuniones"
        actions={
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Nueva Cita
          </Button>
        }
      />

      <DataTable
        columns={columns}
        data={appointments}
        isLoading={isLoading}
        total={appointments.length}
        emptyTitle="Sin citas programadas"
        emptyDescription="Crea una nueva cita para comenzar"
      />

      {/* Create dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nueva Cita</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label>ID del Lead</Label>
              <Input
                type="number"
                value={newLeadId}
                onChange={(e) => setNewLeadId(e.target.value)}
                placeholder="Ej: 42"
                required
              />
            </div>
            <div className="space-y-2">
              <Label>Fecha y hora</Label>
              <Input
                type="datetime-local"
                value={newDate}
                onChange={(e) => setNewDate(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label>Notas (opcional)</Label>
              <Textarea
                value={newNotes}
                onChange={(e) => setNewNotes(e.target.value)}
                placeholder="Comentarios sobre la visita..."
                rows={3}
              />
            </div>
            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setShowCreate(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={creating}>
                {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Crear Cita
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!cancelTarget}
        onOpenChange={(open) => !open && setCancelTarget(null)}
        title="Cancelar cita"
        description="¿Cancelar esta cita? El lead será notificado."
        confirmLabel="Sí, cancelar"
        onConfirm={handleCancel}
        isLoading={actionLoading === cancelTarget?.id}
      />
    </div>
  )
}
