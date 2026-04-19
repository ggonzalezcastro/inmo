import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Textarea } from '@/shared/components/ui/textarea'
import { Label } from '@/shared/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { toast } from 'sonner'
import { useCalendarStore } from '../store/calendarStore'
import { calendarService, APPOINTMENT_TYPE_LABELS } from '../services/calendar.service'
import { LeadSearchCombobox } from './LeadSearchCombobox'
import { getErrorMessage } from '@/shared/types/api'
import { useAuthStore } from '@/features/auth/store/authStore'
import { apiClient } from '@/shared/lib/api-client'
import type { AppointmentTypeEnum, CreateAppointmentPayload } from '../types/calendar.types'

interface LeadOption {
  id: number
  name: string
  phone: string
  email?: string
}

const APPOINTMENT_TYPES = Object.entries(APPOINTMENT_TYPE_LABELS) as [AppointmentTypeEnum, string][]

const DURATION_OPTIONS = [15, 30, 45, 60, 90, 120]

const LOCATION_TYPES: AppointmentTypeEnum[] = ['property_visit', 'office_meeting']

interface AgentOption {
  id: number
  name: string
  email: string
}

interface AppointmentFormModalProps {
  onSaved: () => void
}

export function AppointmentFormModal({ onSaved }: AppointmentFormModalProps) {
  const {
    isFormOpen: isOpen,
    pendingSlot,
    editingAppointmentId: editingId,
    events,
    closeForm,
  } = useCalendarStore()

  const { user, isAdmin, isSuperAdmin } = useAuthStore()
  const canPickAgent = isAdmin() || isSuperAdmin()

  // Load broker agents for the dropdown (admins only)
  const [agents, setAgents] = useState<AgentOption[]>([])
  useEffect(() => {
    if (!canPickAgent) return
    apiClient.get<AgentOption[]>('/api/v1/agents/')
      .then(setAgents)
      .catch(() => {/* non-critical */})
  }, [canPickAgent])

  const toLocalDatetimeValue = (iso: string) => {
    if (!iso) return ''
    const d = new Date(iso)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  }

  const [selectedLead, setSelectedLead] = useState<LeadOption | null>(null)
  const [form, setForm] = useState<{
    agent_id: string
    appointment_type: AppointmentTypeEnum
    start_time: string
    duration_minutes: number
    location: string
    property_address: string
    notes: string
    lead_notes: string
  }>({
    agent_id: user?.id ? String(user.id) : '',
    appointment_type: 'virtual_meeting',
    start_time: '',
    duration_minutes: 60,
    location: '',
    property_address: '',
    notes: '',
    lead_notes: '',
  })

  // Reset form whenever the modal opens (create or edit)
  useEffect(() => {
    if (!isOpen) return

    const existingEvent = editingId
      ? events.find((e) => e.extendedProps.appointmentId === editingId)
      : undefined

    if (existingEvent) {
      // Edit mode — pre-fill everything from the existing event
      setSelectedLead({
        id: existingEvent.extendedProps.leadId,
        name: existingEvent.extendedProps.leadName,
        phone: existingEvent.extendedProps.leadPhone ?? '',
      })
      setForm({
        agent_id: existingEvent.extendedProps.agentId
          ? String(existingEvent.extendedProps.agentId)
          : user?.id ? String(user.id) : '',
        appointment_type: existingEvent.extendedProps.appointmentType,
        start_time: toLocalDatetimeValue(existingEvent.start),
        duration_minutes: existingEvent.extendedProps.durationMinutes,
        location: existingEvent.extendedProps.location ?? '',
        property_address: existingEvent.extendedProps.propertyAddress ?? '',
        notes: existingEvent.extendedProps.notes ?? '',
        lead_notes: '',
      })
    } else {
      // Create mode — clear lead, pre-fill slot date if available
      setSelectedLead(null)
      setForm({
        agent_id: user?.id ? String(user.id) : '',
        appointment_type: 'virtual_meeting',
        start_time: pendingSlot ? toLocalDatetimeValue(pendingSlot.start) : '',
        duration_minutes: 60,
        location: '',
        property_address: '',
        notes: '',
        lead_notes: '',
      })
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, editingId])

  const [submitting, setSubmitting] = useState(false)

  const closeModal = () => {
    setSelectedLead(null)
    closeForm()
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!selectedLead || !form.start_time) {
      toast.error('El lead y la fecha/hora son obligatorios')
      return
    }

    setSubmitting(true)
    try {
      const payload: CreateAppointmentPayload = {
        lead_id: selectedLead.id,
        appointment_type: form.appointment_type,
        start_time: new Date(form.start_time).toISOString(),
        duration_minutes: form.duration_minutes,
        ...(form.agent_id && { agent_id: Number(form.agent_id) }),
        ...(form.location && { location: form.location }),
        ...(form.property_address && { property_address: form.property_address }),
        ...(form.notes && { notes: form.notes }),
        ...(form.lead_notes && { lead_notes: form.lead_notes }),
      }

      if (editingId) {
        await calendarService.updateAppointment(editingId, payload)
        toast.success('Cita actualizada')
      } else {
        await calendarService.createAppointment(payload)
        toast.success('Cita creada')
      }

      onSaved()
      closeModal()
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }

  const showLocation = LOCATION_TYPES.includes(form.appointment_type)

  return (
    <Dialog open={isOpen} onOpenChange={(open) => { if (!open) closeModal() }}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{editingId ? 'Editar cita' : 'Nueva cita'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Lead search */}
          <div className="space-y-1">
            <Label>
              Lead *
              {selectedLead && (
                <span className="text-xs font-normal text-slate-400 ml-2">
                  ID: {selectedLead.id}
                </span>
              )}
            </Label>
            <LeadSearchCombobox
              value={selectedLead}
              onChange={setSelectedLead}
            />
            {!selectedLead && (
              <p className="text-xs text-slate-400">Busca por nombre o teléfono del lead</p>
            )}
          </div>

          {/* Appointment type */}
          <div className="space-y-1">
            <Label>Tipo de cita</Label>
            <Select
              value={form.appointment_type}
              onValueChange={(v) =>
                setForm((f) => ({ ...f, appointment_type: v as AppointmentTypeEnum }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {APPOINTMENT_TYPES.map(([key, label]) => (
                  <SelectItem key={key} value={key}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Date/time */}
          <div className="space-y-1">
            <Label htmlFor="start_time">Fecha y hora *</Label>
            <Input
              id="start_time"
              type="datetime-local"
              value={form.start_time}
              onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value }))}
              required
            />
          </div>

          {/* Duration */}
          <div className="space-y-1">
            <Label>Duración</Label>
            <Select
              value={String(form.duration_minutes)}
              onValueChange={(v) =>
                setForm((f) => ({ ...f, duration_minutes: Number(v) }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DURATION_OPTIONS.map((min) => (
                  <SelectItem key={min} value={String(min)}>
                    {min} minutos
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Agent — select with names for admins, readonly chip for agents */}
          <div className="space-y-1">
            <Label>Agente asignado</Label>
            {canPickAgent ? (
              <Select
                value={form.agent_id}
                onValueChange={(v) => setForm((f) => ({ ...f, agent_id: v }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Seleccionar agente…" />
                </SelectTrigger>
                <SelectContent>
                  {agents.map((a) => (
                    <SelectItem key={a.id} value={String(a.id)}>
                      {a.name}
                      <span className="text-slate-400 text-xs ml-1.5">{a.email}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                <span className="font-medium">{user?.name ?? user?.email}</span>
                <span className="text-xs text-slate-400 ml-auto">(tú)</span>
              </div>
            )}
          </div>

          {/* Location (conditional) */}
          {showLocation && (
            <div className="space-y-1">
              <Label htmlFor="property_address">
                {form.appointment_type === 'property_visit' ? 'Dirección propiedad' : 'Ubicación'}
              </Label>
              <Input
                id="property_address"
                placeholder="Ej: Av. Providencia 1234, Santiago"
                value={
                  form.appointment_type === 'property_visit'
                    ? form.property_address
                    : form.location
                }
                onChange={(e) =>
                  setForm((f) =>
                    form.appointment_type === 'property_visit'
                      ? { ...f, property_address: e.target.value }
                      : { ...f, location: e.target.value }
                  )
                }
              />
            </div>
          )}

          {/* Notes */}
          <div className="space-y-1">
            <Label htmlFor="notes">Notas del agente</Label>
            <Textarea
              id="notes"
              rows={3}
              placeholder="Información adicional para el agente…"
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
            />
          </div>

          {/* Actions */}
          <div className="flex gap-2 justify-end pt-2">
            <Button type="button" variant="outline" onClick={closeModal}>
              Cancelar
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Guardando…' : editingId ? 'Guardar cambios' : 'Crear cita'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
