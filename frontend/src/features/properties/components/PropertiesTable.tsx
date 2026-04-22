import { useState } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { MoreHorizontal, Pencil, Trash2, Eye, BookmarkPlus } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/shared/components/ui/badge'
import { Button } from '@/shared/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu'
import { DataTable } from '@/shared/components/common/DataTable'
import { ConfirmDialog } from '@/shared/components/common/ConfirmDialog'
import { propertiesService } from '../services/properties.service'
import { getErrorMessage } from '@/shared/types/api'
import type { Property, PropertyStatus } from '../types'

interface PropertiesTableProps {
  properties: Property[]
  total: number
  isLoading: boolean
  page: number
  limit: number
  onPageChange: (page: number) => void
  onEdit: (property: Property) => void
  onView: (property: Property) => void
  onDeleted: (id: number) => void
  onReserve?: (property: Property) => void
}

const STATUS_CONFIG: Record<PropertyStatus, { label: string; variant: 'default' | 'secondary' | 'outline' | 'destructive'; className: string }> = {
  available:  { label: 'Disponible', variant: 'default', className: 'bg-emerald-100 text-emerald-800 border-emerald-200' },
  reserved:   { label: 'Reservado',  variant: 'secondary', className: 'bg-amber-100 text-amber-800 border-amber-200' },
  sold:       { label: 'Vendido',    variant: 'secondary', className: 'bg-blue-100 text-blue-800 border-blue-200' },
  rented:     { label: 'Arrendado',  variant: 'secondary', className: 'bg-purple-100 text-purple-800 border-purple-200' },
  archived:   { label: 'Archivado',  variant: 'outline', className: 'bg-slate-100 text-slate-500 border-slate-200' },
}

const TYPE_LABELS: Record<string, string> = {
  departamento: 'Depto.',
  casa: 'Casa',
  terreno: 'Terreno',
  oficina: 'Oficina',
}

function StatusBadge({ status }: { status: PropertyStatus }) {
  const cfg = STATUS_CONFIG[status] ?? { label: status, className: '' }
  return (
    <Badge variant="outline" className={`text-[11px] font-medium ${cfg.className}`}>
      {cfg.label}
    </Badge>
  )
}

export function PropertiesTable({
  properties,
  total,
  isLoading,
  page,
  limit,
  onPageChange,
  onEdit,
  onView,
  onDeleted,
  onReserve,
}: PropertiesTableProps) {
  const [deleteTarget, setDeleteTarget] = useState<Property | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const handleDelete = async () => {
    if (!deleteTarget) return
    setIsDeleting(true)
    try {
      await propertiesService.deleteProperty(deleteTarget.id)
      toast.success('Propiedad archivada')
      onDeleted(deleteTarget.id)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsDeleting(false)
      setDeleteTarget(null)
    }
  }

  const columns: ColumnDef<Property>[] = [
    {
      id: 'name',
      header: 'Propiedad',
      cell: ({ row }) => {
        const p = row.original
        return (
          <div className="flex flex-col gap-0.5 min-w-0">
            <span className="font-medium text-sm truncate max-w-[200px]">{p.name ?? '—'}</span>
            {p.codigo && (
              <span className="text-[11px] text-muted-foreground">{p.codigo}</span>
            )}
            {p.project && (
              <span className="text-[10px] text-blue-700">{p.project.name}</span>
            )}
          </div>
        )
      },
    },
    {
      id: 'type',
      header: 'Tipo',
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">
          {row.original.property_type ? (TYPE_LABELS[row.original.property_type] ?? row.original.property_type) : '—'}
        </span>
      ),
    },
    {
      id: 'commune',
      header: 'Comuna',
      cell: ({ row }) => (
        <span className="text-sm">{row.original.commune ?? '—'}</span>
      ),
    },
    {
      id: 'price_uf',
      header: 'Precio UF',
      cell: ({ row }) => {
        const p = row.original
        return (
          <div className="flex flex-col gap-0.5">
            <span className="text-sm font-medium">
              {p.price_uf != null ? `UF ${p.price_uf.toLocaleString('es-CL')}` : '—'}
            </span>
            {p.price_clp != null && (
              <span className="text-[11px] text-muted-foreground">
                ${(p.price_clp / 1_000_000).toFixed(1)}M
              </span>
            )}
          </div>
        )
      },
    },
    {
      id: 'specs',
      header: 'Dorm. / Baños / m²',
      cell: ({ row }) => {
        const p = row.original
        return (
          <span className="text-sm tabular-nums">
            {p.bedrooms ?? '–'} / {p.bathrooms ?? '–'} / {p.square_meters_useful ?? p.square_meters_total ?? '–'}
          </span>
        )
      },
    },
    {
      id: 'status',
      header: 'Estado',
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => {
        const p = row.original
        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-7 w-7">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onView(p)}>
                <Eye className="mr-2 h-3.5 w-3.5" />
                Ver detalle
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(p)}>
                <Pencil className="mr-2 h-3.5 w-3.5" />
                Editar
              </DropdownMenuItem>
              {onReserve && p.status === 'available' && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => onReserve(p)} className="text-blue-700 focus:text-blue-700">
                    <BookmarkPlus className="mr-2 h-3.5 w-3.5" />
                    Reservar
                  </DropdownMenuItem>
                </>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => setDeleteTarget(p)}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="mr-2 h-3.5 w-3.5" />
                Archivar
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )
      },
    },
  ]

  return (
    <>
      <DataTable
        columns={columns}
        data={properties}
        total={total}
        isLoading={isLoading}
        page={page}
        limit={limit}
        onPageChange={onPageChange}
      />
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="¿Archivar propiedad?"
        description={`"${deleteTarget?.name ?? 'Esta propiedad'}" será marcada como archivada.`}
        confirmLabel="Archivar"
        variant="destructive"
        isLoading={isDeleting}
        onConfirm={handleDelete}
      />
    </>
  )
}
