import { useState } from 'react'
import { ChevronDown, ChevronUp, X } from 'lucide-react'
import { Input } from '@/shared/components/ui/input'
import { Button } from '@/shared/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import type { ProjectFilters, ProjectStatus } from '../types'

interface ProjectFiltersBarProps {
  filters: ProjectFilters
  onFilterChange: (key: keyof ProjectFilters, value: unknown) => void
  onReset: () => void
}

const STATUS_OPTIONS: { value: ProjectStatus | ''; label: string }[] = [
  { value: '', label: 'Todos los estados' },
  { value: 'en_blanco', label: 'En blanco' },
  { value: 'en_construccion', label: 'En construcción' },
  { value: 'en_venta', label: 'En venta' },
  { value: 'entrega_inmediata', label: 'Entrega inmediata' },
  { value: 'terminado', label: 'Terminado' },
  { value: 'agotado', label: 'Agotado' },
]

const UNIT_STATUS_OPTIONS = [
  { value: '', label: 'Disponibilidad' },
  { value: 'available', label: 'Disponible' },
  { value: 'reserved', label: 'Reservada' },
  { value: 'sold', label: 'Vendida' },
  { value: 'rented', label: 'Arrendada' },
]

const PROPERTY_TYPE_OPTIONS = [
  { value: '', label: 'Tipo de unidad' },
  { value: 'departamento', label: 'Departamento' },
  { value: 'casa', label: 'Casa' },
  { value: 'local', label: 'Local comercial' },
  { value: 'oficina', label: 'Oficina' },
  { value: 'bodega', label: 'Bodega' },
  { value: 'estacionamiento', label: 'Estacionamiento' },
]

const BEDROOMS_OPTIONS = [
  { value: '', label: 'Dormitorios' },
  { value: '1', label: '1 dormitorio' },
  { value: '2', label: '2 dormitorios' },
  { value: '3', label: '3 dormitorios' },
  { value: '4', label: '4+ dormitorios' },
]

const BATHROOMS_OPTIONS = [
  { value: '', label: 'Baños' },
  { value: '1', label: '1 baño' },
  { value: '2', label: '2 baños' },
  { value: '3', label: '3+ baños' },
]

const ORIENTATION_OPTIONS = [
  { value: '', label: 'Orientación' },
  { value: 'norte', label: 'Norte' },
  { value: 'sur', label: 'Sur' },
  { value: 'oriente', label: 'Oriente' },
  { value: 'poniente', label: 'Poniente' },
  { value: 'nororiente', label: 'Nororiente' },
  { value: 'norponiente', label: 'Norponiente' },
  { value: 'suroriente', label: 'Suroriente' },
  { value: 'surponiente', label: 'Surponiente' },
]

const UNIT_FILTERS: (keyof ProjectFilters)[] = [
  'unit_status', 'property_type', 'bedrooms', 'bathrooms',
  'min_price_uf', 'max_price_uf', 'min_sqm', 'max_sqm',
  'orientation', 'min_floor', 'max_floor',
]

function hasActiveFilters(filters: ProjectFilters): boolean {
  const checkKeys: (keyof ProjectFilters)[] = [
    'status', 'commune', 'name', 'developer', ...UNIT_FILTERS,
  ]
  return checkKeys.some((k) => filters[k] !== '' && filters[k] != null)
}

function hasActiveUnitFilters(filters: ProjectFilters): boolean {
  return UNIT_FILTERS.some((k) => filters[k] !== '' && filters[k] != null)
}

export function ProjectFiltersBar({ filters, onFilterChange, onReset }: ProjectFiltersBarProps) {
  const [expanded, setExpanded] = useState(false)

  const activeCount = [
    filters.status, filters.commune, filters.name, filters.developer,
    ...UNIT_FILTERS.map((k) => filters[k]),
  ].filter((v) => v !== '' && v != null).length

  return (
    <div className="space-y-2">
      {/* Row 1: basic filters always visible */}
      <div className="flex flex-wrap gap-2 items-center">
        <Input
          placeholder="Nombre del proyecto"
          className="w-44 h-9"
          value={filters.name ?? ''}
          onChange={(e) => onFilterChange('name', e.target.value)}
        />
        <Input
          placeholder="Comuna"
          className="w-36 h-9"
          value={filters.commune ?? ''}
          onChange={(e) => onFilterChange('commune', e.target.value)}
        />
        <Input
          placeholder="Inmobiliaria"
          className="w-36 h-9"
          value={filters.developer ?? ''}
          onChange={(e) => onFilterChange('developer', e.target.value)}
        />
        <Select
          value={filters.status ?? ''}
          onValueChange={(v) => onFilterChange('status', v === '__all__' ? '' : v)}
        >
          <SelectTrigger className="w-44 h-9">
            <SelectValue placeholder="Estado proyecto" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((o) => (
              <SelectItem key={o.value || '__all__'} value={o.value || '__all__'}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant="outline"
          size="sm"
          className="h-9 gap-1"
          onClick={() => setExpanded((v) => !v)}
        >
          Más filtros
          {hasActiveUnitFilters(filters) && (
            <span className="ml-1 bg-primary text-primary-foreground text-xs rounded-full px-1.5 py-0.5 leading-none">
              {UNIT_FILTERS.filter((k) => filters[k] !== '' && filters[k] != null).length}
            </span>
          )}
          {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </Button>

        {activeCount > 0 && (
          <Button variant="ghost" size="sm" className="h-9 gap-1 text-muted-foreground" onClick={onReset}>
            <X className="h-3.5 w-3.5" />
            Limpiar ({activeCount})
          </Button>
        )}
      </div>

      {/* Row 2: unit-level filters (collapsible) */}
      {expanded && (
        <div className="flex flex-wrap gap-2 items-center rounded-lg border border-dashed p-3 bg-muted/30">
          {/* Availability & type */}
          <Select
            value={filters.unit_status ?? ''}
            onValueChange={(v) => onFilterChange('unit_status', v === '__all__' ? '' : v)}
          >
            <SelectTrigger className="w-40 h-9">
              <SelectValue placeholder="Disponibilidad" />
            </SelectTrigger>
            <SelectContent>
              {UNIT_STATUS_OPTIONS.map((o) => (
                <SelectItem key={o.value || '__all__'} value={o.value || '__all__'}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={filters.property_type ?? ''}
            onValueChange={(v) => onFilterChange('property_type', v === '__all__' ? '' : v)}
          >
            <SelectTrigger className="w-44 h-9">
              <SelectValue placeholder="Tipo de unidad" />
            </SelectTrigger>
            <SelectContent>
              {PROPERTY_TYPE_OPTIONS.map((o) => (
                <SelectItem key={o.value || '__all__'} value={o.value || '__all__'}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Bedrooms & bathrooms */}
          <Select
            value={String(filters.bedrooms ?? '')}
            onValueChange={(v) => onFilterChange('bedrooms', v === '__all__' ? '' : v === '' ? '' : Number(v))}
          >
            <SelectTrigger className="w-40 h-9">
              <SelectValue placeholder="Dormitorios" />
            </SelectTrigger>
            <SelectContent>
              {BEDROOMS_OPTIONS.map((o) => (
                <SelectItem key={o.value || '__all__'} value={o.value || '__all__'}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={String(filters.bathrooms ?? '')}
            onValueChange={(v) => onFilterChange('bathrooms', v === '__all__' ? '' : v === '' ? '' : Number(v))}
          >
            <SelectTrigger className="w-32 h-9">
              <SelectValue placeholder="Baños" />
            </SelectTrigger>
            <SelectContent>
              {BATHROOMS_OPTIONS.map((o) => (
                <SelectItem key={o.value || '__all__'} value={o.value || '__all__'}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Price range */}
          <div className="flex items-center gap-1">
            <Input
              type="number"
              placeholder="UF mín"
              className="w-24 h-9"
              value={filters.min_price_uf ?? ''}
              onChange={(e) => onFilterChange('min_price_uf', e.target.value === '' ? '' : Number(e.target.value))}
            />
            <span className="text-muted-foreground text-xs">–</span>
            <Input
              type="number"
              placeholder="UF máx"
              className="w-24 h-9"
              value={filters.max_price_uf ?? ''}
              onChange={(e) => onFilterChange('max_price_uf', e.target.value === '' ? '' : Number(e.target.value))}
            />
          </div>

          {/* Surface range */}
          <div className="flex items-center gap-1">
            <Input
              type="number"
              placeholder="m² mín"
              className="w-24 h-9"
              value={filters.min_sqm ?? ''}
              onChange={(e) => onFilterChange('min_sqm', e.target.value === '' ? '' : Number(e.target.value))}
            />
            <span className="text-muted-foreground text-xs">–</span>
            <Input
              type="number"
              placeholder="m² máx"
              className="w-24 h-9"
              value={filters.max_sqm ?? ''}
              onChange={(e) => onFilterChange('max_sqm', e.target.value === '' ? '' : Number(e.target.value))}
            />
          </div>

          {/* Orientation */}
          <Select
            value={filters.orientation ?? ''}
            onValueChange={(v) => onFilterChange('orientation', v === '__all__' ? '' : v)}
          >
            <SelectTrigger className="w-40 h-9">
              <SelectValue placeholder="Orientación" />
            </SelectTrigger>
            <SelectContent>
              {ORIENTATION_OPTIONS.map((o) => (
                <SelectItem key={o.value || '__all__'} value={o.value || '__all__'}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Floor range */}
          <div className="flex items-center gap-1">
            <Input
              type="number"
              placeholder="Piso mín"
              className="w-24 h-9"
              value={filters.min_floor ?? ''}
              onChange={(e) => onFilterChange('min_floor', e.target.value === '' ? '' : Number(e.target.value))}
            />
            <span className="text-muted-foreground text-xs">–</span>
            <Input
              type="number"
              placeholder="Piso máx"
              className="w-24 h-9"
              value={filters.max_floor ?? ''}
              onChange={(e) => onFilterChange('max_floor', e.target.value === '' ? '' : Number(e.target.value))}
            />
          </div>
        </div>
      )}
    </div>
  )
}
