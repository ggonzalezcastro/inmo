import { useState, useEffect } from 'react'
import { Loader2, Plus, X } from 'lucide-react'
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
import { Textarea } from '@/shared/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { Badge } from '@/shared/components/ui/badge'
import { projectsService } from '../services/projects.service'
import { getErrorMessage } from '@/shared/types/api'
import type { Project, CreateProjectDto, ProjectStatus } from '../types'

interface ProjectFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  project?: Project | null
  onSuccess: (project: Project) => void
  brokerIdOverride?: number
}

const STATUS_OPTIONS: { value: ProjectStatus; label: string }[] = [
  { value: 'en_blanco', label: 'En blanco' },
  { value: 'en_construccion', label: 'En construcción' },
  { value: 'en_venta', label: 'En venta' },
  { value: 'entrega_inmediata', label: 'Entrega inmediata' },
  { value: 'terminado', label: 'Terminado' },
  { value: 'agotado', label: 'Agotado' },
]

export function ProjectFormDialog({
  open,
  onOpenChange,
  project,
  onSuccess,
  brokerIdOverride,
}: ProjectFormDialogProps) {
  const isEditing = !!project

  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [developer, setDeveloper] = useState('')
  const [status, setStatus] = useState<ProjectStatus>('en_venta')
  const [description, setDescription] = useState('')
  const [highlights, setHighlights] = useState('')
  const [commune, setCommune] = useState('')
  const [city, setCity] = useState('')
  const [region, setRegion] = useState('')
  const [address, setAddress] = useState('')
  const [deliveryDate, setDeliveryDate] = useState('')
  const [totalUnits, setTotalUnits] = useState('')
  const [availableUnits, setAvailableUnits] = useState('')
  const [subsidioEligible, setSubsidioEligible] = useState(false)
  const [brochureUrl, setBrochureUrl] = useState('')
  const [virtualTourUrl, setVirtualTourUrl] = useState('')
  const [amenities, setAmenities] = useState<string[]>([])
  const [amenityInput, setAmenityInput] = useState('')
  const [financingOptions, setFinancingOptions] = useState<string[]>([])
  const [financingInput, setFinancingInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (project) {
      setName(project.name ?? '')
      setCode(project.code ?? '')
      setDeveloper(project.developer ?? '')
      setStatus(project.status)
      setDescription(project.description ?? '')
      setHighlights(project.highlights ?? '')
      setCommune(project.commune ?? '')
      setCity(project.city ?? '')
      setRegion(project.region ?? '')
      setAddress(project.address ?? '')
      setDeliveryDate(project.delivery_date ?? '')
      setTotalUnits(project.total_units != null ? String(project.total_units) : '')
      setAvailableUnits(project.available_units != null ? String(project.available_units) : '')
      setSubsidioEligible(project.subsidio_eligible)
      setBrochureUrl(project.brochure_url ?? '')
      setVirtualTourUrl(project.virtual_tour_url ?? '')
      setAmenities(project.common_amenities ?? [])
      setFinancingOptions(project.financing_options ?? [])
    } else {
      setName(''); setCode(''); setDeveloper(''); setStatus('en_venta')
      setDescription(''); setHighlights('')
      setCommune(''); setCity(''); setRegion(''); setAddress('')
      setDeliveryDate(''); setTotalUnits(''); setAvailableUnits('')
      setSubsidioEligible(false); setBrochureUrl(''); setVirtualTourUrl('')
      setAmenities([]); setAmenityInput('')
      setFinancingOptions([]); setFinancingInput('')
    }
  }, [project, open])

  const addAmenity = () => {
    const v = amenityInput.trim()
    if (v && !amenities.includes(v)) setAmenities((prev) => [...prev, v])
    setAmenityInput('')
  }
  const addFinancing = () => {
    const v = financingInput.trim()
    if (v && !financingOptions.includes(v)) setFinancingOptions((prev) => [...prev, v])
    setFinancingInput('')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      toast.error('El nombre del proyecto es obligatorio')
      return
    }
    setIsLoading(true)
    try {
      const data: CreateProjectDto = {
        name: name.trim(),
        ...(code && { code }),
        ...(developer && { developer }),
        status,
        ...(description && { description }),
        ...(highlights && { highlights }),
        ...(commune && { commune }),
        ...(city && { city }),
        ...(region && { region }),
        ...(address && { address }),
        ...(deliveryDate && { delivery_date: deliveryDate }),
        ...(totalUnits && { total_units: Number(totalUnits) }),
        ...(availableUnits && { available_units: Number(availableUnits) }),
        subsidio_eligible: subsidioEligible,
        ...(brochureUrl && { brochure_url: brochureUrl }),
        ...(virtualTourUrl && { virtual_tour_url: virtualTourUrl }),
        ...(amenities.length > 0 && { common_amenities: amenities }),
        ...(financingOptions.length > 0 && { financing_options: financingOptions }),
      }

      const result = isEditing
        ? await projectsService.updateProject(project.id, data, brokerIdOverride)
        : await projectsService.createProject(data, brokerIdOverride)
      toast.success(isEditing ? 'Proyecto actualizado' : 'Proyecto creado')
      onSuccess(result)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Editar proyecto' : 'Nuevo proyecto'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-5">
          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Información básica</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1 col-span-2">
                <Label htmlFor="proj-name">Nombre *</Label>
                <Input id="proj-name" value={name} onChange={(e) => setName(e.target.value)} required placeholder="Ej: Edificio Andes" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="proj-code">Código</Label>
                <Input id="proj-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="Ej: AND-2025" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="proj-developer">Inmobiliaria</Label>
                <Input id="proj-developer" value={developer} onChange={(e) => setDeveloper(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>Estado</Label>
                <Select value={status} onValueChange={(v) => setStatus(v as ProjectStatus)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {STATUS_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="proj-delivery">Fecha de entrega</Label>
                <Input id="proj-delivery" type="date" value={deliveryDate} onChange={(e) => setDeliveryDate(e.target.value)} />
              </div>
            </div>
          </section>

          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Ubicación</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Comuna</Label>
                <Input value={commune} onChange={(e) => setCommune(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>Ciudad</Label>
                <Input value={city} onChange={(e) => setCity(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>Región</Label>
                <Input value={region} onChange={(e) => setRegion(e.target.value)} />
              </div>
              <div className="space-y-1 col-span-2">
                <Label>Dirección</Label>
                <Input value={address} onChange={(e) => setAddress(e.target.value)} />
              </div>
            </div>
          </section>

          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Unidades y comercial</h3>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1">
                <Label>Total unidades</Label>
                <Input type="number" min="0" value={totalUnits} onChange={(e) => setTotalUnits(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>Disponibles</Label>
                <Input type="number" min="0" value={availableUnits} onChange={(e) => setAvailableUnits(e.target.value)} />
              </div>
              <div className="space-y-1 flex items-end">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={subsidioEligible} onChange={(e) => setSubsidioEligible(e.target.checked)} />
                  Apto subsidio
                </label>
              </div>
            </div>
          </section>

          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Descripción</h3>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label>Descripción</Label>
                <Textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>Destacados</Label>
                <Textarea rows={2} value={highlights} onChange={(e) => setHighlights(e.target.value)} />
              </div>
            </div>
          </section>

          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Amenities comunes</h3>
            <div className="flex gap-2">
              <Input
                value={amenityInput}
                onChange={(e) => setAmenityInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addAmenity() } }}
                placeholder="Ej: Piscina, Gym, Conserjería 24h"
              />
              <Button type="button" variant="outline" size="sm" onClick={addAmenity}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            {amenities.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {amenities.map((a) => (
                  <Badge key={a} variant="secondary" className="gap-1">
                    {a}
                    <button type="button" onClick={() => setAmenities((prev) => prev.filter((x) => x !== a))}>
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </section>

          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Financiamiento</h3>
            <div className="flex gap-2">
              <Input
                value={financingInput}
                onChange={(e) => setFinancingInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addFinancing() } }}
                placeholder="Ej: Hipotecario, Pie en cuotas"
              />
              <Button type="button" variant="outline" size="sm" onClick={addFinancing}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            {financingOptions.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {financingOptions.map((a) => (
                  <Badge key={a} variant="secondary" className="gap-1">
                    {a}
                    <button type="button" onClick={() => setFinancingOptions((prev) => prev.filter((x) => x !== a))}>
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </section>

          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Material</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label>Brochure URL</Label>
                <Input value={brochureUrl} onChange={(e) => setBrochureUrl(e.target.value)} />
              </div>
              <div className="space-y-1">
                <Label>Tour virtual URL</Label>
                <Input value={virtualTourUrl} onChange={(e) => setVirtualTourUrl(e.target.value)} />
              </div>
            </div>
          </section>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isLoading}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? 'Guardar cambios' : 'Crear proyecto'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
