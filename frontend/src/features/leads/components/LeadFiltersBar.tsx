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
import { PIPELINE_STAGES } from '@/shared/lib/constants'
import type { LeadFilters } from '../types'

interface LeadFiltersBarProps {
  filters: LeadFilters
  onFilterChange: (key: keyof LeadFilters, value: unknown) => void
  onReset: () => void
}

export function LeadFiltersBar({ filters, onFilterChange, onReset }: LeadFiltersBarProps) {
  const hasActiveFilters =
    filters.search || filters.status || filters.pipeline_stage

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="relative flex-1 min-w-[200px] max-w-xs">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Buscar por nombre o teléfono..."
          value={filters.search ?? ''}
          onChange={(e) => onFilterChange('search', e.target.value)}
          className="pl-9"
        />
      </div>

      <Select
        value={filters.status ?? ''}
        onValueChange={(v) => onFilterChange('status', v === 'all' ? '' : v)}
      >
        <SelectTrigger className="w-36">
          <SelectValue placeholder="Temperatura" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Todas</SelectItem>
          <SelectItem value="cold">Frío</SelectItem>
          <SelectItem value="warm">Tibio</SelectItem>
          <SelectItem value="hot">Caliente</SelectItem>
          <SelectItem value="converted">Convertido</SelectItem>
          <SelectItem value="lost">Perdido</SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={filters.pipeline_stage ?? ''}
        onValueChange={(v) => onFilterChange('pipeline_stage', v === 'all' ? '' : v)}
      >
        <SelectTrigger className="w-44">
          <SelectValue placeholder="Etapa pipeline" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Todas las etapas</SelectItem>
          {PIPELINE_STAGES.map((s) => (
            <SelectItem key={s.key} value={s.key}>
              {s.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {hasActiveFilters && (
        <Button variant="ghost" size="sm" onClick={onReset} className="text-muted-foreground">
          <X className="h-4 w-4 mr-1" />
          Limpiar
        </Button>
      )}
    </div>
  )
}
