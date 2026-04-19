import { useEffect } from 'react'
import { ChevronDown, ChevronRight, Loader2, Plus, Pencil, Trash2 } from 'lucide-react'
import { Badge } from '@/shared/components/ui/badge'
import { Button } from '@/shared/components/ui/button'
import { useProjectUnits, ORPHAN_PROJECT_ID } from '../hooks/useProjectUnits'
import { ProjectUnitsTable } from './ProjectUnitsTable'
import type { Project, OrphanUnitsAggregate } from '../types'

const STATUS_CONFIG: Record<
  string,
  { label: string; className: string }
> = {
  en_blanco: { label: 'En blanco', className: 'bg-slate-100 text-slate-700 border-slate-200' },
  en_construccion: { label: 'En construcción', className: 'bg-amber-100 text-amber-800 border-amber-200' },
  en_venta: { label: 'En venta', className: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  entrega_inmediata: { label: 'Entrega inmediata', className: 'bg-blue-100 text-blue-800 border-blue-200' },
  terminado: { label: 'Terminado', className: 'bg-purple-100 text-purple-800 border-purple-200' },
  agotado: { label: 'Agotado', className: 'bg-rose-100 text-rose-800 border-rose-200' },
}

interface BaseProps {
  expanded: boolean
  onToggle: () => void
  brokerIdOverride?: number
  onAddUnit: (projectId: number | null) => void
  onEditProject?: (project: Project) => void
  onDeleteProject?: (project: Project) => void
  onEditUnit: (unitId: number) => void
}

interface ProjectRowProps extends BaseProps {
  project: Project
}

interface OrphanRowProps extends Omit<BaseProps, 'onEditProject' | 'onDeleteProject'> {
  aggregate: OrphanUnitsAggregate
}

function PriceRange({ min, max }: { min: number | null | undefined; max: number | null | undefined }) {
  if (min == null && max == null) return <span className="text-muted-foreground">—</span>
  if (min === max || max == null) return <span className="font-medium">UF {min?.toLocaleString('es-CL')}</span>
  if (min == null) return <span className="font-medium">≤ UF {max.toLocaleString('es-CL')}</span>
  return (
    <span className="font-medium tabular-nums">
      UF {min.toLocaleString('es-CL')} – {max.toLocaleString('es-CL')}
    </span>
  )
}

export function ProjectAccordionRow({
  project,
  expanded,
  onToggle,
  brokerIdOverride,
  onAddUnit,
  onEditProject,
  onDeleteProject,
  onEditUnit,
}: ProjectRowProps) {
  const { units, isLoading, load } = useProjectUnits(project.id, brokerIdOverride)
  const cfg = STATUS_CONFIG[project.status] ?? { label: project.status, className: 'bg-slate-100' }

  useEffect(() => {
    if (expanded) void load()
  }, [expanded, load])

  return (
    <div className="border rounded-lg bg-white overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-start gap-3 p-4 hover:bg-slate-50 text-left"
      >
        <div className="pt-1">
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </div>
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-sm truncate">{project.name}</span>
            {project.code && (
              <span className="text-[11px] text-muted-foreground">{project.code}</span>
            )}
            <Badge variant="outline" className={`text-[11px] ${cfg.className}`}>
              {cfg.label}
            </Badge>
            {project.subsidio_eligible && (
              <Badge variant="outline" className="text-[11px] bg-teal-50 text-teal-700 border-teal-200">
                Subsidio
              </Badge>
            )}
          </div>
          <div className="text-xs text-muted-foreground flex flex-wrap gap-x-4 gap-y-1">
            {project.developer && <span>{project.developer}</span>}
            {project.commune && <span>{project.commune}</span>}
            {project.delivery_date && <span>Entrega {project.delivery_date}</span>}
          </div>
        </div>
        <div className="flex items-center gap-6 text-xs text-right">
          <div>
            <div className="text-muted-foreground">Unidades</div>
            <div className="font-medium tabular-nums">
              {project.units_available ?? 0} / {project.units_count ?? 0}
            </div>
          </div>
          <div>
            <div className="text-muted-foreground">Precio</div>
            <PriceRange min={project.min_price_uf} max={project.max_price_uf} />
          </div>
        </div>
      </button>

      {expanded && (
        <div className="border-t bg-slate-50/50">
          <div className="flex items-center justify-between px-4 py-2 border-b bg-white">
            <span className="text-xs text-muted-foreground">
              {units ? `${units.length} unidades` : 'Cargando…'}
            </span>
            <div className="flex items-center gap-1">
              {onEditProject && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => onEditProject(project)}
                >
                  <Pencil className="h-3 w-3 mr-1" />
                  Editar proyecto
                </Button>
              )}
              {onDeleteProject && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs text-destructive hover:text-destructive"
                  onClick={() => onDeleteProject(project)}
                >
                  <Trash2 className="h-3 w-3 mr-1" />
                  Eliminar
                </Button>
              )}
              <Button
                size="sm"
                className="h-7 text-xs"
                onClick={() => onAddUnit(project.id)}
              >
                <Plus className="h-3 w-3 mr-1" />
                Agregar unidad
              </Button>
            </div>
          </div>
          <div className="p-2">
            {isLoading && !units ? (
              <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Cargando unidades…
              </div>
            ) : (
              <ProjectUnitsTable units={units ?? []} onEditUnit={onEditUnit} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export function OrphanUnitsAccordionRow({
  aggregate,
  expanded,
  onToggle,
  brokerIdOverride,
  onAddUnit,
  onEditUnit,
}: OrphanRowProps) {
  const { units, isLoading, load } = useProjectUnits(ORPHAN_PROJECT_ID, brokerIdOverride)

  useEffect(() => {
    if (expanded) void load()
  }, [expanded, load])

  return (
    <div className="border border-dashed rounded-lg bg-white overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-start gap-3 p-4 hover:bg-slate-50 text-left"
      >
        <div className="pt-1">
          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </div>
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm">Sin proyecto</span>
            <Badge variant="outline" className="text-[11px] bg-slate-50 text-slate-600">
              Propiedades sueltas
            </Badge>
          </div>
          <div className="text-xs text-muted-foreground">
            Propiedades que no pertenecen a ningún proyecto (usadas, casas individuales).
          </div>
        </div>
        <div className="flex items-center gap-6 text-xs text-right">
          <div>
            <div className="text-muted-foreground">Unidades</div>
            <div className="font-medium tabular-nums">
              {aggregate.units_available} / {aggregate.units_count}
            </div>
          </div>
          <div>
            <div className="text-muted-foreground">Precio</div>
            <PriceRange min={aggregate.min_price_uf} max={aggregate.max_price_uf} />
          </div>
        </div>
      </button>

      {expanded && (
        <div className="border-t bg-slate-50/50">
          <div className="flex items-center justify-between px-4 py-2 border-b bg-white">
            <span className="text-xs text-muted-foreground">
              {units ? `${units.length} unidades` : 'Cargando…'}
            </span>
            <Button size="sm" className="h-7 text-xs" onClick={() => onAddUnit(null)}>
              <Plus className="h-3 w-3 mr-1" />
              Agregar propiedad suelta
            </Button>
          </div>
          <div className="p-2">
            {isLoading && !units ? (
              <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Cargando…
              </div>
            ) : (
              <ProjectUnitsTable units={units ?? []} onEditUnit={onEditUnit} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}
