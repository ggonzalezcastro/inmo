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
import { propertiesService } from '../services/properties.service'
import { projectsService } from '@/features/projects/services/projects.service'
import { getErrorMessage } from '@/shared/types/api'
import type { Property, CreatePropertyDto, PropertyStatus, PropertyType } from '../types'
import type { Project } from '@/features/projects/types'

interface PropertyFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  property?: Property | null
  onSuccess: (property: Property) => void
  brokerIdOverride?: number
  /** Pre-fills the project selector when opening from a project's accordion */
  initialProjectId?: number | null
}

const STATUS_OPTIONS: { value: PropertyStatus; label: string }[] = [
  { value: 'available', label: 'Disponible' },
  { value: 'reserved', label: 'Reservado' },
  { value: 'sold', label: 'Vendido' },
  { value: 'rented', label: 'Arrendado' },
]

const TYPE_OPTIONS: { value: PropertyType; label: string }[] = [
  { value: 'departamento', label: 'Departamento' },
  { value: 'casa', label: 'Casa' },
  { value: 'terreno', label: 'Terreno' },
  { value: 'oficina', label: 'Oficina' },
]

export function PropertyFormDialog({
  open,
  onOpenChange,
  property,
  onSuccess,
  brokerIdOverride,
  initialProjectId = null,
}: PropertyFormDialogProps) {
  const isEditing = !!property

  // Basic
  const [name, setName] = useState('')
  const [codigo, setCodigo] = useState('')
  const [tipologia, setTipologia] = useState('')
  const [projectId, setProjectId] = useState<number | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [propertyType, setPropertyType] = useState<PropertyType | ''>('')
  const [status, setStatus] = useState<PropertyStatus>('available')

  // Location
  const [commune, setCommune] = useState('')
  const [city, setCity] = useState('')
  const [region, setRegion] = useState('')
  const [address, setAddress] = useState('')

  // Specs
  const [bedrooms, setBedrooms] = useState('')
  const [bathrooms, setBathrooms] = useState('')
  const [parkingSpots, setParkingSpots] = useState('')
  const [sqmTotal, setSqmTotal] = useState('')
  const [sqmUseful, setSqmUseful] = useState('')
  const [floorNumber, setFloorNumber] = useState('')
  const [orientation, setOrientation] = useState('')

  // Pricing
  const [priceUf, setPriceUf] = useState('')
  const [priceClp, setPriceClp] = useState('')
  const [listPriceUf, setListPriceUf] = useState('')
  const [listPriceClp, setListPriceClp] = useState('')
  const [offerPriceUf, setOfferPriceUf] = useState('')
  const [offerPriceClp, setOfferPriceClp] = useState('')
  const [hasOffer, setHasOffer] = useState(false)
  const [commonExpenses, setCommonExpenses] = useState('')
  const [subsidioEligible, setSubsidioEligible] = useState(false)

  // Description
  const [description, setDescription] = useState('')
  const [highlights, setHighlights] = useState('')

  // Amenities
  const [amenities, setAmenities] = useState<string[]>([])
  const [amenityInput, setAmenityInput] = useState('')

  // Media
  const [imageUrlInput, setImageUrlInput] = useState('')
  const [imageUrls, setImageUrls] = useState<string[]>([])
  const [floorPlanUrl, setFloorPlanUrl] = useState('')
  const [virtualTourUrl, setVirtualTourUrl] = useState('')

  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (property) {
      setName(property.name ?? '')
      setCodigo(property.codigo ?? '')
      setTipologia(property.tipologia ?? '')
      setProjectId(property.project_id ?? null)
      setPropertyType(property.property_type ?? '')
      setStatus(property.status)
      setCommune(property.commune ?? '')
      setCity(property.city ?? '')
      setRegion(property.region ?? '')
      setAddress(property.address ?? '')
      setBedrooms(property.bedrooms != null ? String(property.bedrooms) : '')
      setBathrooms(property.bathrooms != null ? String(property.bathrooms) : '')
      setParkingSpots(property.parking_spots != null ? String(property.parking_spots) : '')
      setSqmTotal(property.square_meters_total != null ? String(property.square_meters_total) : '')
      setSqmUseful(property.square_meters_useful != null ? String(property.square_meters_useful) : '')
      setFloorNumber(property.floor_number != null ? String(property.floor_number) : '')
      setOrientation(property.orientation ?? '')
      setPriceUf(property.price_uf != null ? String(property.price_uf) : '')
      setPriceClp(property.price_clp != null ? String(property.price_clp) : '')
      setListPriceUf(property.list_price_uf != null ? String(property.list_price_uf) : '')
      setListPriceClp(property.list_price_clp != null ? String(property.list_price_clp) : '')
      setOfferPriceUf(property.offer_price_uf != null ? String(property.offer_price_uf) : '')
      setOfferPriceClp(property.offer_price_clp != null ? String(property.offer_price_clp) : '')
      setHasOffer(!!property.has_offer)
      setCommonExpenses(property.common_expenses_clp != null ? String(property.common_expenses_clp) : '')
      setSubsidioEligible(property.subsidio_eligible)
      setDescription(property.description ?? '')
      setHighlights(property.highlights ?? '')
      setAmenities(property.amenities ?? [])
      setImageUrls((property.images ?? []).map((img) => (typeof img === 'string' ? img : img.url)).filter(Boolean))
      setFloorPlanUrl(property.floor_plan_url ?? '')
      setVirtualTourUrl(property.virtual_tour_url ?? '')
    } else {
      setName(''); setCodigo(''); setTipologia(''); setProjectId(initialProjectId)
      setPropertyType(''); setStatus('available')
      setCommune(''); setCity(''); setRegion(''); setAddress('')
      setBedrooms(''); setBathrooms(''); setParkingSpots(''); setSqmTotal(''); setSqmUseful('')
      setFloorNumber(''); setOrientation('')
      setPriceUf(''); setPriceClp(''); setCommonExpenses(''); setSubsidioEligible(false)
      setListPriceUf(''); setListPriceClp(''); setOfferPriceUf(''); setOfferPriceClp(''); setHasOffer(false)
      setDescription(''); setHighlights('')
      setAmenities([]); setAmenityInput('')
      setImageUrls([]); setImageUrlInput(''); setFloorPlanUrl(''); setVirtualTourUrl('')
    }
  }, [property, open, initialProjectId])

  // Load broker projects for the selector (only when dialog opens, no edit cycles)
  useEffect(() => {
    if (!open) return
    let cancelled = false
    projectsService
      .getProjects({ broker_id: brokerIdOverride ?? null, limit: 200 })
      .then((res) => {
        if (cancelled) return
        setProjects(res.items)
        // Autofill location/subsidio cuando el dialog se abre con un proyecto
        // pre-seleccionado (ej. desde "+ Agregar unidad" del acordeón) y la
        // property es nueva (no estamos editando una existente).
        if (!property && initialProjectId != null) {
          const proj = res.items.find((p) => p.id === initialProjectId)
          if (proj) {
            if (proj.commune) setCommune((c) => c || proj.commune || '')
            if (proj.city) setCity((c) => c || proj.city || '')
            if (proj.region) setRegion((c) => c || proj.region || '')
            if (proj.subsidio_eligible) setSubsidioEligible((v) => v || true)
          }
        }
      })
      .catch(() => {
        if (!cancelled) setProjects([])
      })
    return () => {
      cancelled = true
    }
  }, [open, brokerIdOverride, property, initialProjectId])

  // When user selects a project, autofill commune/city/region/financing/subsidio if empty
  const handleProjectChange = (value: string) => {
    if (value === '__none__') {
      setProjectId(null)
      return
    }
    const id = Number(value)
    setProjectId(id)
    const proj = projects.find((p) => p.id === id)
    if (!proj) return
    if (!commune && proj.commune) setCommune(proj.commune)
    if (!city && proj.city) setCity(proj.city)
    if (!region && proj.region) setRegion(proj.region)
    if (!subsidioEligible && proj.subsidio_eligible) setSubsidioEligible(true)
  }

  const addAmenity = () => {
    const v = amenityInput.trim()
    if (v && !amenities.includes(v)) setAmenities((prev) => [...prev, v])
    setAmenityInput('')
  }

  const addImageUrl = () => {
    const v = imageUrlInput.trim()
    if (v) setImageUrls((prev) => [...prev, v])
    setImageUrlInput('')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      const data: CreatePropertyDto = {
        ...(name && { name }),
        ...(codigo && { codigo }),
        ...(tipologia && { tipologia }),
        project_id: projectId,
        ...(propertyType && { property_type: propertyType }),
        status,
        ...(commune && { commune }),
        ...(city && { city }),
        ...(region && { region }),
        ...(address && { address }),
        ...(bedrooms && { bedrooms: Number(bedrooms) }),
        ...(bathrooms && { bathrooms: Number(bathrooms) }),
        ...(parkingSpots && { parking_spots: Number(parkingSpots) }),
        ...(sqmTotal && { square_meters_total: Number(sqmTotal) }),
        ...(sqmUseful && { square_meters_useful: Number(sqmUseful) }),
        ...(floorNumber && { floor_number: Number(floorNumber) }),
        ...(orientation && { orientation }),
        ...(priceUf && { price_uf: Number(priceUf) }),
        ...(priceClp && { price_clp: Number(priceClp) }),
        ...(listPriceUf && { list_price_uf: Number(listPriceUf) }),
        ...(listPriceClp && { list_price_clp: Number(listPriceClp) }),
        ...(offerPriceUf && { offer_price_uf: Number(offerPriceUf) }),
        ...(offerPriceClp && { offer_price_clp: Number(offerPriceClp) }),
        has_offer: hasOffer,
        ...(commonExpenses && { common_expenses_clp: Number(commonExpenses) }),
        subsidio_eligible: subsidioEligible,
        ...(description && { description }),
        ...(highlights && { highlights }),
        ...(amenities.length > 0 && { amenities }),
        ...(imageUrls.length > 0 && { images: imageUrls.map((url, i) => ({ url, order: i })) }),
        ...(floorPlanUrl && { floor_plan_url: floorPlanUrl }),
        ...(virtualTourUrl && { virtual_tour_url: virtualTourUrl }),
      }

      const result = isEditing
        ? await propertiesService.updateProperty(property.id, data, brokerIdOverride)
        : await propertiesService.createProperty(data, brokerIdOverride)

      toast.success(isEditing ? 'Propiedad actualizada' : 'Propiedad creada')
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
          <DialogTitle>{isEditing ? 'Editar propiedad' : 'Nueva propiedad'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Basic */}
          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Información básica</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="name">Nombre</Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej: Edificio La Moneda" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="code">Código</Label>
                <Input id="code" value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="Ej: Depto 502" />
              </div>
              <div className="space-y-1">
                <Label>Tipo</Label>
                <Select value={propertyType} onValueChange={(v) => setPropertyType(v as PropertyType)}>
                  <SelectTrigger><SelectValue placeholder="Seleccionar tipo" /></SelectTrigger>
                  <SelectContent>
                    {TYPE_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label>Estado</Label>
                <Select value={status} onValueChange={(v) => setStatus(v as PropertyStatus)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {STATUS_OPTIONS.map((o) => <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="tipologia">Tipología</Label>
                <Input id="tipologia" value={tipologia} onChange={(e) => setTipologia(e.target.value)} placeholder="Ej: 2D2B, A1" />
              </div>
              <div className="space-y-1">
                <Label>Proyecto</Label>
                <Select
                  value={projectId == null ? '__none__' : String(projectId)}
                  onValueChange={handleProjectChange}
                >
                  <SelectTrigger><SelectValue placeholder="Sin proyecto" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">Sin proyecto</SelectItem>
                    {projects.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.name}{p.code ? ` · ${p.code}` : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </section>

          {/* Location */}
          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Ubicación</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="commune">Comuna</Label>
                <Input id="commune" value={commune} onChange={(e) => setCommune(e.target.value)} placeholder="Ej: Las Condes" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="city">Ciudad</Label>
                <Input id="city" value={city} onChange={(e) => setCity(e.target.value)} placeholder="Ej: Santiago" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="region">Región</Label>
                <Input id="region" value={region} onChange={(e) => setRegion(e.target.value)} placeholder="Ej: Región Metropolitana" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="address">Dirección</Label>
                <Input id="address" value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Ej: Av. Apoquindo 4000" />
              </div>
            </div>
          </section>

          {/* Specs */}
          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Especificaciones</h3>
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: 'Dormitorios', value: bedrooms, setter: setBedrooms },
                { label: 'Baños', value: bathrooms, setter: setBathrooms },
                { label: 'Estacionamientos', value: parkingSpots, setter: setParkingSpots },
                { label: 'm² totales', value: sqmTotal, setter: setSqmTotal },
                { label: 'm² útiles', value: sqmUseful, setter: setSqmUseful },
                { label: 'Piso', value: floorNumber, setter: setFloorNumber },
              ].map(({ label, value, setter }) => (
                <div key={label} className="space-y-1">
                  <Label>{label}</Label>
                  <Input type="number" value={value} onChange={(e) => setter(e.target.value)} min="0" />
                </div>
              ))}
              <div className="space-y-1 col-span-3">
                <Label htmlFor="orientation">Orientación</Label>
                <Input id="orientation" value={orientation} onChange={(e) => setOrientation(e.target.value)} placeholder="Ej: Norte, Sur-Oriente" />
              </div>
            </div>
          </section>

          {/* Pricing */}
          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Precios</h3>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1">
                <Label htmlFor="price_uf">Precio UF (actual)</Label>
                <Input id="price_uf" type="number" value={priceUf} onChange={(e) => setPriceUf(e.target.value)} placeholder="Ej: 3500" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="price_clp">Precio CLP (actual)</Label>
                <Input id="price_clp" type="number" value={priceClp} onChange={(e) => setPriceClp(e.target.value)} placeholder="Ej: 120000000" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="gastos">Gastos comunes</Label>
                <Input id="gastos" type="number" value={commonExpenses} onChange={(e) => setCommonExpenses(e.target.value)} placeholder="CLP mensual" />
              </div>

              <div className="space-y-1">
                <Label htmlFor="list_uf">Precio lista UF</Label>
                <Input id="list_uf" type="number" value={listPriceUf} onChange={(e) => setListPriceUf(e.target.value)} placeholder="Precio publicado" />
              </div>
              <div className="space-y-1">
                <Label htmlFor="list_clp">Precio lista CLP</Label>
                <Input id="list_clp" type="number" value={listPriceClp} onChange={(e) => setListPriceClp(e.target.value)} />
              </div>
              <div />

              <div className="space-y-1">
                <Label htmlFor="offer_uf">Precio oferta UF</Label>
                <Input id="offer_uf" type="number" value={offerPriceUf} onChange={(e) => setOfferPriceUf(e.target.value)} placeholder="Precio promocional" disabled={!hasOffer} />
              </div>
              <div className="space-y-1">
                <Label htmlFor="offer_clp">Precio oferta CLP</Label>
                <Input id="offer_clp" type="number" value={offerPriceClp} onChange={(e) => setOfferPriceClp(e.target.value)} disabled={!hasOffer} />
              </div>
              <div className="flex items-center gap-2 pt-6">
                <input
                  type="checkbox"
                  id="has_offer"
                  checked={hasOffer}
                  onChange={(e) => setHasOffer(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300"
                />
                <Label htmlFor="has_offer" className="cursor-pointer">Oferta disponible</Label>
              </div>

              <div className="col-span-3 flex items-center gap-2">
                <input
                  type="checkbox"
                  id="subsidio"
                  checked={subsidioEligible}
                  onChange={(e) => setSubsidioEligible(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300"
                />
                <Label htmlFor="subsidio" className="cursor-pointer">Elegible para subsidio habitacional</Label>
              </div>
            </div>
          </section>

          {/* Description */}
          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Descripción</h3>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label htmlFor="description">Descripción</Label>
                <Textarea id="description" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} placeholder="Descripción completa de la propiedad..." />
              </div>
              <div className="space-y-1">
                <Label htmlFor="highlights">Highlights</Label>
                <Textarea id="highlights" value={highlights} onChange={(e) => setHighlights(e.target.value)} rows={2} placeholder="Puntos destacados..." />
              </div>
            </div>
          </section>

          {/* Amenities */}
          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Amenidades</h3>
            <div className="space-y-2">
              <div className="flex gap-2">
                <Input
                  value={amenityInput}
                  onChange={(e) => setAmenityInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addAmenity() } }}
                  placeholder="Ej: Piscina, Gimnasio..."
                  className="flex-1"
                />
                <Button type="button" variant="outline" size="sm" onClick={addAmenity}>
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              {amenities.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {amenities.map((a) => (
                    <Badge key={a} variant="secondary" className="gap-1 pr-1">
                      {a}
                      <button
                        type="button"
                        onClick={() => setAmenities((prev) => prev.filter((x) => x !== a))}
                        className="hover:text-destructive"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Media */}
          <section>
            <h3 className="text-sm font-semibold mb-3 text-muted-foreground uppercase tracking-wide">Multimedia</h3>
            <div className="space-y-3">
              <div className="space-y-1">
                <Label>URLs de imágenes</Label>
                <div className="flex gap-2">
                  <Input
                    value={imageUrlInput}
                    onChange={(e) => setImageUrlInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addImageUrl() } }}
                    placeholder="https://..."
                    className="flex-1"
                  />
                  <Button type="button" variant="outline" size="sm" onClick={addImageUrl}>
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                {imageUrls.length > 0 && (
                  <div className="flex flex-col gap-1 mt-1">
                    {imageUrls.map((url, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <span className="flex-1 truncate text-muted-foreground">{url}</span>
                        <button type="button" onClick={() => setImageUrls((prev) => prev.filter((_, idx) => idx !== i))}>
                          <X className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="floor_plan">Plano URL</Label>
                  <Input id="floor_plan" value={floorPlanUrl} onChange={(e) => setFloorPlanUrl(e.target.value)} placeholder="https://..." />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="tour">Tour virtual URL</Label>
                  <Input id="tour" value={virtualTourUrl} onChange={(e) => setVirtualTourUrl(e.target.value)} placeholder="https://..." />
                </div>
              </div>
            </div>
          </section>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? 'Guardar cambios' : 'Crear propiedad'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
