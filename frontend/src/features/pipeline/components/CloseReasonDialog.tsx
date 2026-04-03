import { useState } from 'react'
import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/shared/components/ui/dialog'
import { PIPELINE_STAGES } from '@/shared/lib/constants'
import type { Lead } from '@/features/leads/types'

const PERDIDO_REASONS = [
  { value: 'precio', label: 'Precio alto' },
  { value: 'ubicacion', label: 'Ubicación no conveniente' },
  { value: 'no_califica', label: 'No califica financieramente' },
  { value: 'competencia', label: 'Eligió competencia' },
  { value: 'sin_respuesta', label: 'Sin respuesta' },
  { value: 'otro', label: 'Otro' },
]

const GANADO_REASONS = [
  { value: 'compra_directa', label: 'Compra directa' },
  { value: 'financiamiento_aprobado', label: 'Financiamiento aprobado' },
  { value: 'reserva', label: 'Reserva' },
  { value: 'otro', label: 'Otro' },
]

interface CloseReasonDialogProps {
  lead: Lead
  targetStage: 'ganado' | 'perdido'
  onConfirm: (reason: string, detail: string) => void
  onCancel: () => void
}

export function CloseReasonDialog({ lead, targetStage, onConfirm, onCancel }: CloseReasonDialogProps) {
  const [reason, setReason] = useState('')
  const [detail, setDetail] = useState('')

  const reasons = targetStage === 'perdido' ? PERDIDO_REASONS : GANADO_REASONS
  const stageLabel = PIPELINE_STAGES.find((s) => s.key === targetStage)?.label ?? targetStage

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onCancel() }}>
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>
            Mover a <span className={targetStage === 'ganado' ? 'text-emerald-600' : 'text-rose-600'}>{stageLabel}</span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <p className="text-sm text-muted-foreground">
            ¿Cuál es el motivo para <strong>{lead.name}</strong>?
          </p>

          <div className="space-y-2">
            {reasons.map((r) => (
              <label
                key={r.value}
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  reason === r.value
                    ? 'border-[#1A56DB] bg-[#EBF2FF]'
                    : 'border-border hover:border-[#1A56DB]/40 hover:bg-[#F8FAFC]'
                }`}
              >
                <input
                  type="radio"
                  name="close_reason"
                  value={r.value}
                  checked={reason === r.value}
                  onChange={() => setReason(r.value)}
                  className="accent-[#1A56DB]"
                />
                <span className="text-sm font-medium">{r.label}</span>
              </label>
            ))}
          </div>

          <textarea
            placeholder="Notas adicionales (opcional)"
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
            rows={2}
            className="w-full text-sm rounded-lg border border-border px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-[#1A56DB] focus:border-[#1A56DB] placeholder:text-muted-foreground"
          />
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" size="sm" onClick={onCancel}>
            Cancelar
          </Button>
          <Button
            size="sm"
            disabled={!reason}
            onClick={() => onConfirm(reason, detail)}
            className={targetStage === 'ganado' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-rose-600 hover:bg-rose-700'}
          >
            Confirmar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
