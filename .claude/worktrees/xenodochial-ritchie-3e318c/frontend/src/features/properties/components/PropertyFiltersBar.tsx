import { Search, X } from 'lucide-react'
import { Input } from '@/shared/components/ui/input'
import { Button } from '@/shared/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import type { PropertyFilters, PropertyStatus, PropertyType } from '../types'

interface PropertyFiltersBarProps {
  filters: PropertyFilters
  onFilterChange: (key: keyof PropertyFilters, value: unknown) => void
  onReset: () => void
}

const STATUS_OPTIONS: { value: PropertyStatus; label: string }[] = [
  { value: 'available', label: 'Disponible' },
  { value: 'reserved', label: 'Reservado' },
  { value: 'sold', label: 'Vendido' },
  { value: 'rented', label: 'Arrendado' },
  { value: 'archived', label: 'Archivado' },
]

const TYPE_OPTIONS: { value: PropertyType; label: string }[] = [
  { value: 'departamento', label: 'Departamento' },
  { value: 'casa', label: 'Casa' },
  { value: 'terreno', label: 'Terreno' },
  { value: 'oficina', label: 'Oficina' },
]

const BEDROOM_OPTIONS = [
  { value: '1', label: '1+' },
  { value: '2', label: '2+' },
  { value: '3', label: '3+' },
  { value: '4', label: '4+' },
  { value: '5', label: '5+' },
]

export function PropertyFiltersBar({ filters, onFilterChange, onReset }: PropertyFiltersBarProps) {
  const hasActiveFilters =
    !!filters.status ||
    !!filters.property_type ||
    !!filters.commune ||
    !!filters.min_price_uf ||
    !!filters.max_price_uf ||
    !!filters.min_bedrooms

  return (
    <div className="flex flex-wrap gap-2 items-center">
      {/* Commune search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          placeholder="Comuna..."
          value={filters.commune ?? ''}
          onChange={(e) => onFilterChange('commune', e.target.value)}
          className="pl-8 h-8 w-36 text-sm"
        />
      </div>

      {/* Status */}
      <Select
        value={filters.status ?? ''}
        onValueChange={(v) => onFilterChange('status', v === 'all' ? '' : v)}
      >
        <SelectTrigger className="h-8 w-36 text-sm">
          <SelectValue placeholder="Estado" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Todos los estados</SelectItem>
          {STATUS_OPTIONS.map((o) => (
            <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Type */}
      <Select
        value={filters.property_type ?? ''}
        onValueChange={(v) => onFilterChange('property_type', v === 'all' ? '' : v)}
      >
        <SelectTrigger className="h-8 w-36 text-sm">
          <SelectValue placeholder="Tipo" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Todos los tipos</SelectItem>
          {TYPE_OPTIONS.map((o) => (
            <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* Price range */}
      <Input
        type="number"
        placeholder="Min UF"
        value={filters.min_price_uf ?? ''}
        onChange={(e) => onFilterChange('min_price_uf', e.target.value ? Number(e.target.value) : '')}
        className="h-8 w-24 text-sm"
      />
      <Input
        type="number"
        placeholder="Max UF"
        value={filters.max_price_uf ?? ''}
        onChange={(e) => onFilterChange('max_price_uf', e.target.value ? Number(e.target.value) : '')}
        className="h-8 w-24 text-sm"
      />

      {/* Bedrooms */}
      <Select
        value={String(filters.min_bedrooms ?? '')}
        onValueChange={(v) => onFilterChange('min_bedrooms', v === 'all' ? '' : Number(v))}
      >
        <SelectTrigger className="h-8 w-28 text-sm">
          <SelectValue placeholder="Dormitorios" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Cualquier cantidad</SelectItem>
          {BEDROOM_OPTIONS.map((o) => (
            <SelectItem key={o.value} value={o.value}>{o.label} dorm.</SelectItem>
          ))}
        </SelectContent>
      </Select>

      {hasActiveFilters && (
        <Button variant="ghost" size="sm" className="h-8 gap-1 text-sm" onClick={onReset}>
          <X className="h-3.5 w-3.5" />
          Limpiar
        </Button>
      )}
    </div>
  )
}
