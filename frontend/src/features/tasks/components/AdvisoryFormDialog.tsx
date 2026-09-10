import { useEffect, useState } from 'react'
import { Handshake, Loader2 } from 'lucide-react'
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
import { Textarea } from '@/shared/components/ui/textarea'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { getErrorMessage } from '@/shared/types/api'
import { tasksService } from '../services/tasks.service'
import type { AdvisoryChannel, AgentOption, LeadAdvisory } from '../types'

interface AdvisoryFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  leadId: number
  leadName?: string | null
  defaultAdvisorId?: number | null
  onSaved: (advisory: LeadAdvisory) => void
}

function toLocalInput(date = new Date()) {
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 16)
}

const CHANNELS: Array<{ value: AdvisoryChannel; label: string }> = [
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'phone', label: 'Llamada telefónica' },
  { value: 'video_call', label: 'Videollamada' },
  { value: 'property_visit', label: 'Visita a propiedad' },
  { value: 'in_person', label: 'Reunión presencial' },
  { value: 'other', label: 'Otro canal' },
]

export function AdvisoryFormDialog({
  open,
  onOpenChange,
  leadId,
  leadName,
  defaultAdvisorId,
  onSaved,
}: AdvisoryFormDialogProps) {
  const { role } = usePermissions()
  const isBrokerAdmin = role === 'admin'
  const [channel, setChannel] = useState<AdvisoryChannel>('whatsapp')
  const [occurredAt, setOccurredAt] = useState(toLocalInput())
  const [advisorId, setAdvisorId] = useState('')
  const [notes, setNotes] = useState('')
  const [agents, setAgents] = useState<AgentOption[]>([])
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    setChannel('whatsapp')
    setOccurredAt(toLocalInput())
    setAdvisorId(String(defaultAdvisorId ?? ''))
    setNotes('')
  }, [defaultAdvisorId, open])

  useEffect(() => {
    if (!open || !isBrokerAdmin) return
    tasksService.listAgents().then(setAgents).catch(() => {
      toast.error('No se pudieron cargar los ejecutivos')
    })
  }, [isBrokerAdmin, open])

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!occurredAt) return
    if (isBrokerAdmin && !advisorId) {
      toast.error('Selecciona el ejecutivo que realizó la asesoría')
      return
    }

    setIsSaving(true)
    try {
      const saved = await tasksService.createAdvisory(leadId, {
        channel,
        occurred_at: new Date(occurredAt).toISOString(),
        notes: notes.trim() || null,
        ...(isBrokerAdmin ? { advisor_id: Number(advisorId) } : {}),
      })
      toast.success('Asesoría registrada')
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
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">
            <Handshake className="h-5 w-5" />
          </div>
          <DialogTitle>Registrar asesoría</DialogTitle>
          <DialogDescription>
            Deja constancia de la interacción comercial realizada con {leadName || 'este lead'}.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {isBrokerAdmin && (
            <div className="space-y-1.5">
              <Label htmlFor="advisory-advisor">Ejecutivo</Label>
              <select
                id="advisory-advisor"
                value={advisorId}
                onChange={(event) => setAdvisorId(event.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="">Seleccionar ejecutivo…</option>
                {agents.map((agent) => (
                  <option key={agent.id} value={agent.id}>{agent.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="advisory-channel">Canal</Label>
              <select
                id="advisory-channel"
                value={channel}
                onChange={(event) => setChannel(event.target.value as AdvisoryChannel)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {CHANNELS.map((item) => (
                  <option key={item.value} value={item.value}>{item.label}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="advisory-date">Fecha y hora</Label>
              <Input
                id="advisory-date"
                type="datetime-local"
                value={occurredAt}
                max={toLocalInput()}
                onChange={(event) => setOccurredAt(event.target.value)}
                required
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="advisory-notes">Resumen opcional</Label>
            <Textarea
              id="advisory-notes"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              maxLength={1000}
              rows={3}
              placeholder="Ej. Revisamos alternativas, presupuesto y próximos pasos."
              className="resize-none"
            />
            <p className="text-[11px] text-muted-foreground">
              El registro será histórico y no podrá editarse ni eliminarse.
            </p>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSaving || !occurredAt || (isBrokerAdmin && !advisorId)}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Registrar asesoría
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
