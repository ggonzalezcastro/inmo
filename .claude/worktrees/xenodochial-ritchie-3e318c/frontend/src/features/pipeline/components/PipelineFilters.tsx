import { useState, useEffect } from 'react'
import { Search, X } from 'lucide-react'
import { Input } from '@/shared/components/ui/input'
import { Button } from '@/shared/components/ui/button'
import { pipelineService } from '../services/pipeline.service'

export interface PipelineFilterValues {
  search: string
  assignedTo: string
  calificacion: string
  created_from: string
  created_to: string
}

const EMPTY_FILTERS: PipelineFilterValues = {
  search: '',
  assignedTo: '',
  calificacion: '',
  created_from: '',
  created_to: '',
}

interface PipelineFiltersProps {
  filters: PipelineFilterValues
  onChange: (filters: PipelineFilterValues) => void
}

const CALIFICACION_OPTIONS = [
  { value: '', label: 'Todas' },
  { value: 'CALIFICADO', label: 'Calificado' },
  { value: 'POTENCIAL', label: 'Potencial' },
  { value: 'NO_CALIFICADO', label: 'No calificado' },
]

export function PipelineFilters({ filters, onChange }: PipelineFiltersProps) {
  const [agents, setAgents] = useState<Array<{ id: number; name: string }>>([])

  useEffect(() => {
    pipelineService.listAgents().then(setAgents).catch(() => {})
  }, [])

  const isActive = Object.values(filters).some(Boolean)

  function set(key: keyof PipelineFilterValues, value: string) {
    onChange({ ...filters, [key]: value })
  }

  return (
    <div className="flex flex-wrap items-center gap-2 px-4 py-2 bg-muted/30 border-b">
      {/* Search */}
      <div className="relative min-w-[180px]">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          value={filters.search}
          onChange={(e) => set('search', e.target.value)}
          placeholder="Nombre o teléfono…"
          className="h-8 pl-8 text-sm"
        />
      </div>

      {/* Assigned agent */}
      <select
        value={filters.assignedTo}
        onChange={(e) => set('assignedTo', e.target.value)}
        className="h-8 rounded-md border border-input bg-background px-2.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      >
        <option value="">Todos los agentes</option>
        <option value="unassigned">Sin asignar</option>
        {agents.map((a) => (
          <option key={a.id} value={String(a.id)}>{a.name}</option>
        ))}
      </select>

      {/* Calificacion */}
      <select
        value={filters.calificacion}
        onChange={(e) => set('calificacion', e.target.value)}
        className="h-8 rounded-md border border-input bg-background px-2.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
      >
        {CALIFICACION_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {/* Date range */}
      <input
        type="date"
        value={filters.created_from}
        onChange={(e) => set('created_from', e.target.value)}
        className="h-8 rounded-md border border-input bg-background px-2.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        title="Desde"
      />
      <input
        type="date"
        value={filters.created_to}
        onChange={(e) => set('created_to', e.target.value)}
        className="h-8 rounded-md border border-input bg-background px-2.5 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        title="Hasta"
      />

      {/* Clear */}
      {isActive && (
        <Button
          variant="ghost"
          size="sm"
          className="h-8 px-2 text-muted-foreground hover:text-foreground"
          onClick={() => onChange(EMPTY_FILTERS)}
        >
          <X className="h-3.5 w-3.5 mr-1" />
          Limpiar
        </Button>
      )}
    </div>
  )
}
