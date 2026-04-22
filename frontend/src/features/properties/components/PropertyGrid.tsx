import { PropertyCard } from './PropertyCard'
import type { Property } from '../types'

interface PropertyGridProps {
  properties: Property[]
  onView?: (property: Property) => void
  onEdit?: (property: Property) => void
  onReserve?: (property: Property) => void
}

export function PropertyGrid({ properties, onView, onEdit, onReserve }: PropertyGridProps) {
  if (properties.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground text-sm">
        No se encontraron propiedades
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {properties.map((property) => (
        <PropertyCard
          key={property.id}
          property={property}
          onView={onView}
          onEdit={onEdit}
          onReserve={onReserve}
        />
      ))}
    </div>
  )
}
