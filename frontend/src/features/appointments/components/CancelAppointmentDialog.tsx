import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { Button } from '@/shared/components/ui/button'
import { Textarea } from '@/shared/components/ui/textarea'
import { Label } from '@/shared/components/ui/label'
import { AlertTriangle } from 'lucide-react'
import { toast } from 'sonner'
import { calendarService } from '../services/calendar.service'
import { getErrorMessage } from '@/shared/types/api'
import type { CalendarEvent } from '../types/calendar.types'

interface CancelAppointmentDialogProps {
  open: boolean
  appointmentId: number
  leadName: string
  onClose: () => void
  onCancelled: (updated: CalendarEvent) => void
}

export function CancelAppointmentDialog({
  open,
  appointmentId,
  leadName,
  onClose,
  onCancelled,
}: CancelAppointmentDialogProps) {
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)

  const handleCancel = async () => {
    setLoading(true)
    try {
      const updated = await calendarService.cancelAppointment(
        appointmentId,
        reason.trim() || undefined
      )
      toast.success('Cita cancelada')
      setReason('')
      onCancelled(updated)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(open) => { if (!open) onClose() }}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-rose-500" />
            ¿Cancelar cita?
          </DialogTitle>
        </DialogHeader>

        <p className="text-sm text-slate-600">
          Se cancelará la cita con <strong>{leadName}</strong>.
        </p>

        <div className="space-y-1">
          <Label htmlFor="reason">Razón de cancelación (opcional)</Label>
          <Textarea
            id="reason"
            rows={3}
            placeholder="Ej: El lead solicitó reagendar…"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>

        <div className="flex gap-2 justify-end mt-2">
          <Button variant="outline" size="sm" disabled={loading} onClick={onClose}>
            Volver
          </Button>
          <Button
            size="sm"
            variant="destructive"
            disabled={loading}
            onClick={handleCancel}
          >
            {loading ? 'Cancelando…' : 'Cancelar cita'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
