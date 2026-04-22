import { Bed, Bath, Square, Car, MapPin, Eye, Pencil, BookmarkPlus } from 'lucide-react'
import { Badge } from '@/shared/components/ui/badge'
import { Button } from '@/shared/components/ui/button'
import type { Property, PropertyStatus } from '../types'

const STATUS_BADGE_CONFIG: Record<PropertyStatus, { label: string; className: string }> = {
  reserved: { label: 'Reservada', className: 'bg-yellow-100 text-yellow-800 border-yellow-200' },
  sold:      { label: 'Vendida',   className: 'bg-red-100 text-red-800 border-red-200' },
  available: { label: 'Disponible', className: 'bg-green-100 text-green-800 border-green-200' },
  rented:    { label: 'Arrendada', className: 'bg-purple-100 text-purple-800 border-purple-200' },
  archived:  { label: 'Archivada', className: 'bg-slate-100 text-slate-500 border-slate-200' },
}

const DIMMED_STATUSES: PropertyStatus[] = ['reserved', 'sold', 'archived']

interface PropertyCardProps {
  property: Property
  onView?: (property: Property) => void
  onEdit?: (property: Property) => void
  onReserve?: (property: Property) => void
}

export function PropertyCard({ property: p, onView, onEdit, onReserve }: PropertyCardProps) {
  const statusCfg = STATUS_BADGE_CONFIG[p.status] ?? { label: p.status, className: '' }
  const isDimmed = DIMMED_STATUSES.includes(p.status)
  const firstImage = p.images?.[0]
  const imageUrl = firstImage && typeof firstImage === 'object' ? firstImage.url : (firstImage as string | undefined)

  const displayPrice = p.has_offer && p.offer_price_uf != null
    ? p.offer_price_uf
    : (p.list_price_uf ?? p.price_uf)

  return (
    <div
      className={`group relative rounded-xl border bg-white shadow-sm overflow-hidden flex flex-col transition-shadow hover:shadow-md ${isDimmed ? 'opacity-75' : ''}`}
    >
      {/* Image area with status badge overlay */}
      <div className="relative aspect-[4/3] bg-slate-100 overflow-hidden shrink-0">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={p.name ?? ''}
            className="w-full h-full object-cover transition-transform group-hover:scale-105"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-slate-300">
            <Square className="h-10 w-10" />
          </div>
        )}

        {/* Status badge — top-right corner */}
        <div className="absolute top-2 right-2">
          <Badge variant="outline" className={`text-[11px] font-semibold shadow-sm ${statusCfg.className}`}>
            {statusCfg.label}
          </Badge>
        </div>

        {/* Offer badge — top-left corner */}
        {p.has_offer && (
          <div className="absolute top-2 left-2">
            <Badge variant="outline" className="text-[11px] font-semibold bg-rose-50 text-rose-700 border-rose-200 shadow-sm">
              OFERTA
            </Badge>
          </div>
        )}

        {/* Dim overlay for non-available properties */}
        {isDimmed && (
          <div className="absolute inset-0 bg-white/20 pointer-events-none" />
        )}
      </div>

      {/* Card body */}
      <div className="flex flex-col gap-2 p-3 flex-1">
        {/* Name + code */}
        <div>
          <p className="font-semibold text-sm truncate text-slate-900 leading-tight">
            {p.name ?? 'Sin nombre'}
          </p>
          {p.tipologia && (
            <p className="text-[11px] text-muted-foreground">{p.tipologia}</p>
          )}
          {p.project && (
            <p className="text-[11px] text-blue-700 truncate">{p.project.name}</p>
          )}
        </div>

        {/* Price */}
        {displayPrice != null && (
          <div>
            <p className={`text-base font-bold leading-tight ${p.has_offer ? 'text-rose-600' : 'text-slate-900'}`}>
              UF {displayPrice.toLocaleString('es-CL')}
            </p>
            {p.has_offer && p.list_price_uf != null && (
              <p className="text-[11px] text-muted-foreground line-through">
                UF {p.list_price_uf.toLocaleString('es-CL')}
              </p>
            )}
          </div>
        )}

        {/* Specs */}
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
          {p.bedrooms != null && (
            <span className="flex items-center gap-1">
              <Bed className="h-3 w-3" />{p.bedrooms} dorm.
            </span>
          )}
          {p.bathrooms != null && (
            <span className="flex items-center gap-1">
              <Bath className="h-3 w-3" />{p.bathrooms} baños
            </span>
          )}
          {(p.square_meters_useful ?? p.square_meters_total) != null && (
            <span className="flex items-center gap-1">
              <Square className="h-3 w-3" />{p.square_meters_useful ?? p.square_meters_total} m²
            </span>
          )}
          {p.parking_spots != null && p.parking_spots > 0 && (
            <span className="flex items-center gap-1">
              <Car className="h-3 w-3" />{p.parking_spots} est.
            </span>
          )}
        </div>

        {/* Location */}
        {(p.commune || p.city) && (
          <p className="text-[11px] text-muted-foreground flex items-center gap-1 truncate">
            <MapPin className="h-3 w-3 shrink-0" />
            {[p.commune, p.city].filter(Boolean).join(', ')}
          </p>
        )}
      </div>

      {/* Actions footer */}
      {(onView || onEdit || (onReserve && p.status === 'available')) && (
        <div className="flex gap-1.5 px-3 pb-3">
          {onView && (
            <Button
              variant="outline"
              size="sm"
              className="flex-1 h-7 text-xs gap-1"
              onClick={() => onView(p)}
            >
              <Eye className="h-3 w-3" /> Ver
            </Button>
          )}
          {onEdit && (
            <Button
              variant="outline"
              size="sm"
              className="flex-1 h-7 text-xs gap-1"
              onClick={() => onEdit(p)}
            >
              <Pencil className="h-3 w-3" /> Editar
            </Button>
          )}
          {onReserve && p.status === 'available' && (
            <Button
              size="sm"
              className="flex-1 h-7 text-xs gap-1 bg-blue-600 hover:bg-blue-700 text-white"
              onClick={() => onReserve(p)}
            >
              <BookmarkPlus className="h-3 w-3" /> Reservar
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
