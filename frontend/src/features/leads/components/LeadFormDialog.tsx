import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/shared/components/ui/dialog'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { leadsService } from '../services/leads.service'
import { getErrorMessage } from '@/shared/types/api'
import type { Lead, CreateLeadDto } from '../types'

interface LeadFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  lead?: Lead | null
  onSuccess: (lead: Lead) => void
}

export function LeadFormDialog({ open, onOpenChange, lead, onSuccess }: LeadFormDialogProps) {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const isEditing = !!lead

  useEffect(() => {
    if (lead) {
      setName(lead.name)
      setPhone(lead.phone)
      setEmail(lead.email ?? '')
    } else {
      setName('')
      setPhone('')
      setEmail('')
    }
  }, [lead, open])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      const data: CreateLeadDto = { name, phone, email: email || undefined }
      const result = isEditing
        ? await leadsService.updateLead(lead.id, data)
        : await leadsService.createLead(data)
      toast.success(isEditing ? 'Lead actualizado' : 'Lead creado')
      onSuccess(result)
      onOpenChange(false)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Editar Lead' : 'Nuevo Lead'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Nombre</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="Nombre completo"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="phone">Teléfono</Label>
            <Input
              id="phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
              placeholder="+56 9 1234 5678"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email (opcional)</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="correo@ejemplo.com"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" type="button" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? 'Guardar' : 'Crear Lead'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
