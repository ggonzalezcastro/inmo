import { Pencil, BookmarkPlus } from 'lucide-react'
import { Badge } from '@/shared/components/ui/badge'
import { Button } from '@/shared/components/ui/button'
import type { ProjectUnitSummary } from '../types'

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  available: { label: 'Disponible', className: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  reserved: { label: 'Reservado', className: 'bg-amber-100 text-amber-800 border-amber-200' },
  sold: { label: 'Vendido', className: 'bg-blue-100 text-blue-800 border-blue-200' },
  rented: { label: 'Arrendado', className: 'bg-purple-100 text-purple-800 border-purple-200' },
  archived: { label: 'Archivado', className: 'bg-slate-100 text-slate-500 border-slate-200' },
}

interface ProjectUnitsTableProps {
  units: ProjectUnitSummary[]
  onEditUnit: (id: number) => void
  onReserveUnit?: (unit: ProjectUnitSummary) => void
}

export function ProjectUnitsTable({ units, onEditUnit, onReserveUnit }: ProjectUnitsTableProps) {
  if (units.length === 0) {
    return (
      <div className="text-center text-sm text-muted-foreground py-8">
        No hay unidades cargadas en este proyecto todavía.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b">
            <th className="text-left font-medium px-2 py-2">Código</th>
            <th className="text-left font-medium px-2 py-2">Tipología</th>
            <th className="text-left font-medium px-2 py-2">Dorm/Baño/m²</th>
            <th className="text-left font-medium px-2 py-2">Piso</th>
            <th className="text-left font-medium px-2 py-2">Orient.</th>
            <th className="text-right font-medium px-2 py-2">Precio UF</th>
            <th className="text-left font-medium px-2 py-2">Estado</th>
            <th className="px-2 py-2" />
          </tr>
        </thead>
        <tbody>
          {units.map((u) => {
            const cfg = STATUS_CONFIG[u.status] ?? { label: u.status, className: '' }
            return (
              <tr key={u.id} className="border-b last:border-b-0 hover:bg-white">
                <td className="px-2 py-2 font-medium">{u.codigo ?? `#${u.id}`}</td>
                <td className="px-2 py-2">
                  {u.tipologia ? (
                    <Badge variant="outline" className="text-[11px]">
                      {u.tipologia}
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
                <td className="px-2 py-2 tabular-nums">
                  {u.bedrooms ?? '–'} / {u.bathrooms ?? '–'} / {u.square_meters_useful ?? '–'}
                </td>
                <td className="px-2 py-2 tabular-nums">{u.floor_number ?? '—'}</td>
                <td className="px-2 py-2">{u.orientation ?? '—'}</td>
                <td className="px-2 py-2 text-right tabular-nums">
                  {u.has_offer && u.offer_price_uf != null ? (
                    <span>
                      <span className="text-rose-600 font-medium">
                        UF {u.offer_price_uf.toLocaleString('es-CL')}
                      </span>
                      {u.price_uf != null && (
                        <span className="text-[11px] text-muted-foreground line-through ml-1">
                          {u.price_uf.toLocaleString('es-CL')}
                        </span>
                      )}
                    </span>
                  ) : u.price_uf != null ? (
                    <span className="font-medium">UF {u.price_uf.toLocaleString('es-CL')}</span>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
                <td className="px-2 py-2">
                  <Badge variant="outline" className={`text-[11px] ${cfg.className}`}>
                    {cfg.label}
                  </Badge>
                </td>
                <td className="px-2 py-2 text-right">
                  <div className="flex items-center justify-end gap-1">
                    {onReserveUnit && u.status === 'available' && (
                      <Button
                        size="sm"
                        className="h-7 px-2 text-xs gap-1 bg-blue-600 hover:bg-blue-700 text-white"
                        onClick={() => onReserveUnit(u)}
                        title="Reservar unidad"
                      >
                        <BookmarkPlus className="h-3.5 w-3.5" />
                        Reservar
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => onEditUnit(u.id)}
                      title="Editar unidad"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
