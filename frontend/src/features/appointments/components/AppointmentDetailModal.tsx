import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { Button } from '@/shared/components/ui/button'
import { Badge } from '@/shared/components/ui/badge'
import { Separator } from '@/shared/components/ui/separator'
import {
  Phone, User, Calendar, Clock, MapPin, Link as LinkIcon,
  CheckCircle, XCircle, Pencil, Trash2, AlertTriangle,
} from 'lucide-react'
import { toast } from 'sonner'
import { useCalendarStore } from '../store/calendarStore'
import { calendarService } from '../services/calendar.service'
import { CancelAppointmentDialog } from './CancelAppointmentDialog'
import { APPOINTMENT_TYPE_LABELS, APPOINTMENT_TYPE_ICONS } from '../services/calendar.service'
import { APPOINTMENT_STATUS_CONFIG } from '@/shared/lib/constants'
import { getErrorMessage } from '@/shared/types/api'
import { formatDateTime } from '@/shared/lib/utils'
import type { CalendarEvent } from '../types/calendar.types'

interface AppointmentDetailModalProps {
  onClose: () => void
  onDelete: (id: number) => void
  onUpdate: (id: number, data: Partial<CalendarEvent>) => void
}

export function AppointmentDetailModal({
  onClose,
  onDelete,
  onUpdate,
}: AppointmentDetailModalProps) {
  const { selectedEvent } = useCalendarStore()
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [showCancel, setShowCancel] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  if (!selectedEvent) return null

  const props = selectedEvent.extendedProps
  const statusCfg = APPOINTMENT_STATUS_CONFIG[props.status]
  const isOpen = !!selectedEvent
  const isFinal = props.status === 'cancelled' || props.status === 'completed'

  const handleConfirm = async () => {
    setActionLoading('confirm')
    try {
      const updated = await calendarService.confirmAppointment(props.appointmentId)
      onUpdate(props.appointmentId, updated)
      toast.success('Cita confirmada')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setActionLoading(null)
    }
  }

  const handleDelete = async () => {
    setActionLoading('delete')
    try {
      await calendarService.deleteAppointment(props.appointmentId)
      onDelete(props.appointmentId)
      onClose()
      toast.success('Cita eliminada')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setActionLoading(null)
      setShowDeleteConfirm(false)
    }
  }

  const handleEdit = () => {
    useCalendarStore.getState().openEditForm(props.appointmentId)
    onClose()
  }

  return (
    <>
      <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose() }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <span>{APPOINTMENT_TYPE_ICONS[props.appointmentType]}</span>
              <span>{APPOINTMENT_TYPE_LABELS[props.appointmentType]}</span>
              <Badge variant="outline" className={statusCfg?.className ?? ''}>
                {statusCfg?.label ?? props.status}
              </Badge>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-3 text-sm">
            {/* Lead info */}
            <div className="flex items-center gap-2 text-slate-700">
              <User className="h-4 w-4 text-slate-400 shrink-0" />
              <span className="font-medium">{props.leadName}</span>
              {props.leadPhone && (
                <a
                  href={`tel:${props.leadPhone}`}
                  className="flex items-center gap-1 text-blue-600 hover:underline ml-auto"
                >
                  <Phone className="h-3 w-3" />
                  {props.leadPhone}
                </a>
              )}
            </div>

            {/* Agent */}
            {props.agentName && (
              <div className="flex items-center gap-2 text-slate-600">
                <User className="h-4 w-4 text-slate-400 shrink-0" />
                <span>Agente: {props.agentName}</span>
              </div>
            )}

            <Separator />

            {/* Date/time */}
            <div className="flex items-center gap-2 text-slate-700">
              <Calendar className="h-4 w-4 text-slate-400 shrink-0" />
              <span>{formatDateTime(selectedEvent.start)}</span>
            </div>

            <div className="flex items-center gap-2 text-slate-700">
              <Clock className="h-4 w-4 text-slate-400 shrink-0" />
              <span>{props.durationMinutes} minutos</span>
            </div>

            {/* Location */}
            {(props.location || props.propertyAddress) && (
              <div className="flex items-center gap-2 text-slate-700">
                <MapPin className="h-4 w-4 text-slate-400 shrink-0" />
                <span>{props.propertyAddress ?? props.location}</span>
              </div>
            )}

            {/* Meet link */}
            {props.meetUrl && (
              <div className="flex items-center gap-2">
                <LinkIcon className="h-4 w-4 text-slate-400 shrink-0" />
                <a
                  href={props.meetUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline truncate"
                >
                  Unirse a la reunión
                </a>
              </div>
            )}

            {/* Notes */}
            {props.notes && (
              <>
                <Separator />
                <div className="text-slate-600">
                  <p className="font-medium text-xs uppercase tracking-wide text-slate-400 mb-1">Notas</p>
                  <p className="whitespace-pre-wrap">{props.notes}</p>
                </div>
              </>
            )}

            {/* Cancellation reason */}
            {props.cancellationReason && (
              <div className="flex items-start gap-2 rounded-md bg-rose-50 border border-rose-200 p-3">
                <AlertTriangle className="h-4 w-4 text-rose-500 mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs font-medium text-rose-700">Razón de cancelación</p>
                  <p className="text-sm text-rose-600">{props.cancellationReason}</p>
                </div>
              </div>
            )}
          </div>

          {/* Actions */}
          {!isFinal && (
            <>
              <Separator />
              <div className="flex flex-wrap gap-2 pt-1">
                {props.status === 'scheduled' && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="text-emerald-700 border-emerald-200 hover:bg-emerald-50"
                    disabled={actionLoading === 'confirm'}
                    onClick={handleConfirm}
                  >
                    <CheckCircle className="h-4 w-4 mr-1" />
                    {actionLoading === 'confirm' ? 'Confirmando…' : 'Confirmar'}
                  </Button>
                )}

                <Button size="sm" variant="outline" onClick={handleEdit}>
                  <Pencil className="h-4 w-4 mr-1" />
                  Editar
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  className="text-rose-600 border-rose-200 hover:bg-rose-50"
                  onClick={() => setShowCancel(true)}
                >
                  <XCircle className="h-4 w-4 mr-1" />
                  Cancelar
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  className="ml-auto text-slate-500 hover:text-rose-600"
                  disabled={actionLoading === 'delete'}
                  onClick={() => setShowDeleteConfirm(true)}
                >
                  <Trash2 className="h-4 w-4 mr-1" />
                  Eliminar
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Cancel with reason */}
      <CancelAppointmentDialog
        open={showCancel}
        leadName={props.leadName}
        appointmentId={props.appointmentId}
        onClose={() => setShowCancel(false)}
        onCancelled={(updated) => {
          onUpdate(props.appointmentId, updated)
          setShowCancel(false)
          onClose()
        }}
      />

      {/* Delete confirmation */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>¿Eliminar cita?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-slate-600">
            Se eliminará la cita con <strong>{props.leadName}</strong>. Esta acción no se puede deshacer.
          </p>
          <div className="flex gap-2 justify-end mt-2">
            <Button variant="outline" size="sm" onClick={() => setShowDeleteConfirm(false)}>
              Cancelar
            </Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={actionLoading === 'delete'}
              onClick={handleDelete}
            >
              {actionLoading === 'delete' ? 'Eliminando…' : 'Eliminar'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
