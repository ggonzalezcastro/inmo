/**
 * StartCallDialog — modal to select call_mode + call_purpose before initiating.
 */
import { useState } from 'react'
import { Phone } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/shared/components/ui/dialog'
import { Button } from '@/shared/components/ui/button'
import { Label } from '@/shared/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import type { CallMode, CallPurpose } from '../types'
import { CALL_PURPOSE_LABELS } from '../types'

interface StartCallDialogProps {
  open: boolean
  leadName: string
  leadPhone: string
  onCancel: () => void
  onConfirm: (mode: CallMode, purpose: CallPurpose) => void
  loading?: boolean
}

const CALL_MODES: { value: CallMode; label: string; description: string }[] = [
  {
    value: 'transcriptor',
    label: 'Transcriptor',
    description: 'Tú hablas, la IA transcribe y resume',
  },
  {
    value: 'ai_agent',
    label: 'Agente IA',
    description: 'La IA conduce la conversación (requiere perfil configurado)',
  },
]

export function StartCallDialog({
  open,
  leadName,
  leadPhone,
  onCancel,
  onConfirm,
  loading = false,
}: StartCallDialogProps) {
  const [mode, setMode] = useState<CallMode>('transcriptor')
  const [purpose, setPurpose] = useState<CallPurpose>('calificacion_inicial')

  const handleConfirm = () => {
    onConfirm(mode, purpose)
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onCancel()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Phone className="h-4 w-4 text-green-600" />
            Iniciar llamada
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-1 py-1">
          <p className="text-sm font-medium">{leadName}</p>
          <p className="text-xs text-muted-foreground">{leadPhone}</p>
        </div>

        <div className="space-y-4 py-2">
          {/* Call mode */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold uppercase text-muted-foreground">
              Modo
            </Label>
            <div className="grid grid-cols-2 gap-2">
              {CALL_MODES.map((m) => (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => setMode(m.value)}
                  className={`rounded-lg border p-3 text-left transition-colors ${
                    mode === m.value
                      ? 'border-primary bg-primary/5 ring-1 ring-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  <p className="text-sm font-medium">{m.label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-snug">{m.description}</p>
                </button>
              ))}
            </div>
          </div>

          {/* Call purpose */}
          <div className="space-y-1.5">
            <Label htmlFor="call-purpose" className="text-xs font-semibold uppercase text-muted-foreground">
              Propósito
            </Label>
            <Select value={purpose} onValueChange={(v) => setPurpose(v as CallPurpose)}>
              <SelectTrigger id="call-purpose" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.entries(CALL_PURPOSE_LABELS) as [CallPurpose, string][]).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onCancel} disabled={loading}>
            Cancelar
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={loading}
            className="bg-green-600 hover:bg-green-700 text-white"
          >
            {loading ? 'Iniciando…' : 'Llamar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
