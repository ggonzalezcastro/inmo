import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
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
import { LeadSearchCombobox } from '@/features/appointments/components/LeadSearchCombobox'
import { dealsApi } from '@/features/deals/services/dealsApi'
import { getErrorMessage } from '@/shared/types/api'
import type { Property } from '../types'
import type { DeliveryType } from '@/features/deals/types'

interface LeadOption {
  id: number
  name: string
  phone: string
  email?: string
}

interface ReservePropertyModalProps {
  property: Property
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

export function ReservePropertyModal({
  property,
  open,
  onOpenChange,
  onSuccess,
}: ReservePropertyModalProps) {
  const [selectedLead, setSelectedLead] = useState<LeadOption | null>(null)
  const [deliveryType, setDeliveryType] = useState<DeliveryType>('desconocida')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!selectedLead) {
      toast.error('Selecciona un lead para continuar')
      return
    }

    setLoading(true)
    try {
      await dealsApi.create({
        lead_id: selectedLead.id,
        property_id: property.id,
        delivery_type: deliveryType,
      })
      toast.success(`Deal creado para ${selectedLead.name} — ${property.name ?? 'Propiedad'}`)
      onOpenChange(false)
      setSelectedLead(null)
      setDeliveryType('desconocida')
      onSuccess?.()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Reservar propiedad</DialogTitle>
          <DialogDescription>
            <span className="font-medium text-slate-700">{property.name ?? `Propiedad #${property.id}`}</span>
            {property.tipologia && (
              <span className="text-slate-500"> · {property.tipologia}</span>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          <div className="flex flex-col gap-1.5">
            <Label>Lead</Label>
            <LeadSearchCombobox
              value={selectedLead}
              onChange={setSelectedLead}
              placeholder="Buscar lead por nombre o teléfono…"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Tipo de entrega</Label>
            <Select value={deliveryType} onValueChange={(v) => setDeliveryType(v as DeliveryType)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="inmediata">Inmediata</SelectItem>
                <SelectItem value="futura">Futura</SelectItem>
                <SelectItem value="desconocida">Por definir</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            Cancelar
          </Button>
          <Button onClick={handleSubmit} disabled={loading || !selectedLead}>
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Crear deal
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
