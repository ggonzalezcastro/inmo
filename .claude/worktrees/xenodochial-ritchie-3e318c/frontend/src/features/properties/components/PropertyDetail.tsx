import { X, MapPin, Bed, Bath, Square, Car, Building2, ExternalLink } from 'lucide-react'
import { Button } from '@/shared/components/ui/button'
import { Badge } from '@/shared/components/ui/badge'
import { Separator } from '@/shared/components/ui/separator'
import { formatDate } from '@/shared/lib/utils'
import type { Property, PropertyStatus } from '../types'

interface PropertyDetailProps {
  property: Property
  onClose: () => void
  onEdit: (property: Property) => void
}

const STATUS_CONFIG: Record<PropertyStatus, { label: string; className: string }> = {
  available: { label: 'Disponible', className: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  reserved:  { label: 'Reservado',  className: 'bg-amber-100 text-amber-800 border-amber-200' },
  sold:      { label: 'Vendido',    className: 'bg-blue-100 text-blue-800 border-blue-200' },
  rented:    { label: 'Arrendado',  className: 'bg-purple-100 text-purple-800 border-purple-200' },
  archived:  { label: 'Archivado',  className: 'bg-slate-100 text-slate-500 border-slate-200' },
}

export function PropertyDetail({ property: p, onClose, onEdit }: PropertyDetailProps) {
  const statusCfg = STATUS_CONFIG[p.status] ?? { label: p.status, className: '' }
  const firstImage = p.images?.[0]
  const firstImageUrl = firstImage && typeof firstImage === 'object' ? firstImage.url : firstImage as string | undefined

  return (
    <div className="w-[360px] border-l border-[#E2EAF4] bg-white flex flex-col h-full overflow-y-auto shrink-0">
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-[#E2EAF4] sticky top-0 bg-white z-10">
        <div className="flex-1 min-w-0">
          <h2 className="font-semibold text-sm truncate">{p.name ?? 'Sin nombre'}</h2>
          {p.internal_code && (
            <p className="text-[11px] text-muted-foreground">{p.internal_code}</p>
          )}
        </div>
        <div className="flex items-center gap-1.5 ml-2 shrink-0">
          <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => onEdit(p)}>
            Editar
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Image */}
      {firstImageUrl && (
        <div className="aspect-video w-full overflow-hidden bg-slate-100 shrink-0">
          <img src={firstImageUrl} alt={p.name ?? ''} className="w-full h-full object-cover" />
        </div>
      )}

      <div className="p-4 space-y-4 flex-1">
        {/* Status + Type */}
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className={`text-[11px] ${statusCfg.className}`}>
            {statusCfg.label}
          </Badge>
          {p.property_type && (
            <Badge variant="secondary" className="text-[11px] capitalize">
              {p.property_type}
            </Badge>
          )}
          {p.subsidio_eligible && (
            <Badge variant="outline" className="text-[11px] bg-green-50 text-green-700 border-green-200">
              Subsidio
            </Badge>
          )}
        </div>

        {/* Price */}
        <div>
          {p.price_uf != null && (
            <p className="text-2xl font-bold text-slate-900">
              UF {p.price_uf.toLocaleString('es-CL')}
            </p>
          )}
          {p.price_clp != null && (
            <p className="text-sm text-muted-foreground">
              ${p.price_clp.toLocaleString('es-CL')} CLP
            </p>
          )}
          {p.common_expenses_clp != null && (
            <p className="text-xs text-muted-foreground mt-0.5">
              Gastos comunes: ${p.common_expenses_clp.toLocaleString('es-CL')}/mes
            </p>
          )}
        </div>

        {/* Location */}
        {(p.commune || p.city || p.address) && (
          <div className="flex gap-2 text-sm text-muted-foreground">
            <MapPin className="h-4 w-4 mt-0.5 shrink-0 text-slate-400" />
            <div>
              {p.address && <p>{p.address}</p>}
              <p>{[p.commune, p.city, p.region].filter(Boolean).join(', ')}</p>
            </div>
          </div>
        )}

        {/* Key specs grid */}
        <div className="grid grid-cols-3 gap-2">
          {p.bedrooms != null && (
            <div className="flex flex-col items-center gap-1 bg-slate-50 rounded-lg p-2">
              <Bed className="h-4 w-4 text-slate-400" />
              <span className="text-sm font-semibold">{p.bedrooms}</span>
              <span className="text-[10px] text-muted-foreground">Dorm.</span>
            </div>
          )}
          {p.bathrooms != null && (
            <div className="flex flex-col items-center gap-1 bg-slate-50 rounded-lg p-2">
              <Bath className="h-4 w-4 text-slate-400" />
              <span className="text-sm font-semibold">{p.bathrooms}</span>
              <span className="text-[10px] text-muted-foreground">Baños</span>
            </div>
          )}
          {(p.square_meters_useful ?? p.square_meters_total) != null && (
            <div className="flex flex-col items-center gap-1 bg-slate-50 rounded-lg p-2">
              <Square className="h-4 w-4 text-slate-400" />
              <span className="text-sm font-semibold">{p.square_meters_useful ?? p.square_meters_total}</span>
              <span className="text-[10px] text-muted-foreground">m²</span>
            </div>
          )}
          {p.parking_spots != null && p.parking_spots > 0 && (
            <div className="flex flex-col items-center gap-1 bg-slate-50 rounded-lg p-2">
              <Car className="h-4 w-4 text-slate-400" />
              <span className="text-sm font-semibold">{p.parking_spots}</span>
              <span className="text-[10px] text-muted-foreground">Estac.</span>
            </div>
          )}
          {p.floor_number != null && (
            <div className="flex flex-col items-center gap-1 bg-slate-50 rounded-lg p-2">
              <Building2 className="h-4 w-4 text-slate-400" />
              <span className="text-sm font-semibold">{p.floor_number}</span>
              <span className="text-[10px] text-muted-foreground">Piso</span>
            </div>
          )}
          {p.orientation && (
            <div className="flex flex-col items-center gap-1 bg-slate-50 rounded-lg p-2">
              <span className="text-lg">🧭</span>
              <span className="text-[11px] font-semibold">{p.orientation}</span>
              <span className="text-[10px] text-muted-foreground">Orient.</span>
            </div>
          )}
        </div>

        {/* Description */}
        {p.description && (
          <div>
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Descripción</h4>
            <p className="text-sm text-slate-700 leading-relaxed">{p.description}</p>
          </div>
        )}

        {/* Highlights */}
        {p.highlights && (
          <div>
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Highlights</h4>
            <p className="text-sm text-slate-700 leading-relaxed">{p.highlights}</p>
          </div>
        )}

        {/* Amenities */}
        {p.amenities && p.amenities.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Amenidades</h4>
            <div className="flex flex-wrap gap-1.5">
              {p.amenities.map((a) => (
                <Badge key={a} variant="secondary" className="text-[11px]">{a}</Badge>
              ))}
            </div>
          </div>
        )}

        {/* Financing options */}
        {p.financing_options && p.financing_options.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Financiamiento</h4>
            <div className="flex flex-wrap gap-1.5">
              {p.financing_options.map((f) => (
                <Badge key={f} variant="outline" className="text-[11px]">{f}</Badge>
              ))}
            </div>
          </div>
        )}

        {/* Nearby places */}
        {p.nearby_places && p.nearby_places.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Lugares cercanos</h4>
            <ul className="space-y-1">
              {p.nearby_places.map((place, i) => (
                <li key={i} className="text-sm text-muted-foreground flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-300 shrink-0" />
                  {place.name}
                  {place.distance_m && <span className="text-[11px]">({place.distance_m}m)</span>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Media links */}
        {(p.floor_plan_url || p.virtual_tour_url) && (
          <div className="flex gap-2">
            {p.floor_plan_url && (
              <a href={p.floor_plan_url} target="_blank" rel="noopener noreferrer">
                <Button variant="outline" size="sm" className="h-7 text-xs gap-1">
                  <ExternalLink className="h-3 w-3" /> Plano
                </Button>
              </a>
            )}
            {p.virtual_tour_url && (
              <a href={p.virtual_tour_url} target="_blank" rel="noopener noreferrer">
                <Button variant="outline" size="sm" className="h-7 text-xs gap-1">
                  <ExternalLink className="h-3 w-3" /> Tour virtual
                </Button>
              </a>
            )}
          </div>
        )}

        <Separator />

        {/* Metadata */}
        <div className="text-[11px] text-muted-foreground space-y-0.5">
          {p.created_at && <p>Creado: {formatDate(p.created_at)}</p>}
          {p.updated_at && <p>Actualizado: {formatDate(p.updated_at)}</p>}
          {p.year_built && <p>Año construcción: {p.year_built}</p>}
        </div>
      </div>
    </div>
  )
}
