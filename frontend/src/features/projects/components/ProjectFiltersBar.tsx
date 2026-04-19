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

export function ProjectFiltersBar({ filters, onFilterChange, onReset }: ProjectFiltersBarProps) {
  return (
    <div className="flex flex-wrap gap-2 items-center">
      <Input
        placeholder="Comuna"
        className="w-40 h-9"
        value={filters.commune ?? ''}
        onChange={(e) => onFilterChange('commune', e.target.value)}
      />
      <Select
        value={filters.status ?? ''}
        onValueChange={(v) => onFilterChange('status', v === '__all__' ? '' : v)}
      >
        <SelectTrigger className="w-44 h-9">
          <SelectValue placeholder="Estado" />
        </SelectTrigger>
        <SelectContent>
          {STATUS_OPTIONS.map((o) => (
            <SelectItem key={o.value || '__all__'} value={o.value || '__all__'}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Button variant="ghost" size="sm" onClick={onReset}>
        Limpiar
      </Button>
    </div>
  )
}
