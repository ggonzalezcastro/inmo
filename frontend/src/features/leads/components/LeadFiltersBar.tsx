import { Search, X, SlidersHorizontal } from 'lucide-react'
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
    filters.search ||
    filters.status ||
    filters.pipeline_stage ||
    filters.dicom_status ||
    filters.created_from ||
    filters.created_to

  return (
    <div className="space-y-2">
      {/* Row 1: search + selects */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar por nombre, teléfono o email…"
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

        <Select
          value={filters.dicom_status ?? ''}
          onValueChange={(v) => onFilterChange('dicom_status', v === 'all' ? '' : v)}
        >
          <SelectTrigger className="w-36">
            <SelectValue placeholder="DICOM" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todo DICOM</SelectItem>
            <SelectItem value="clean">Limpio</SelectItem>
            <SelectItem value="has_debt">Con deuda</SelectItem>
            <SelectItem value="unknown">Desconocido</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Row 2: date range + clear */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          <SlidersHorizontal className="h-3.5 w-3.5" />
          <span className="text-xs">Creado entre:</span>
        </div>
        <Input
          type="date"
          value={filters.created_from ?? ''}
          onChange={(e) => onFilterChange('created_from', e.target.value)}
          className="w-36 h-8 text-sm"
        />
        <span className="text-xs text-muted-foreground">y</span>
        <Input
          type="date"
          value={filters.created_to ?? ''}
          onChange={(e) => onFilterChange('created_to', e.target.value)}
          className="w-36 h-8 text-sm"
        />

        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={onReset} className="text-muted-foreground h-8">
            <X className="h-4 w-4 mr-1" />
            Limpiar filtros
          </Button>
        )}
      </div>
    </div>
  )
}
