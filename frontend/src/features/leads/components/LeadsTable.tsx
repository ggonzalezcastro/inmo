import { useState } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { MoreHorizontal, Pencil, Trash2, Eye } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu'
import { DataTable } from '@/shared/components/common/DataTable'
import { StatusBadge } from '@/shared/components/common/StatusBadge'
import { ScoreBadge } from '@/shared/components/common/ScoreBadge'
import { PipelineStageBadge } from '@/shared/components/common/PipelineStageBadge'
import { QualificationBadge } from '@/shared/components/common/QualificationBadge'
import { ConfirmDialog } from '@/shared/components/common/ConfirmDialog'
import { formatRelativeTime } from '@/shared/lib/utils'
import { leadsService } from '../services/leads.service'
import { getErrorMessage } from '@/shared/types/api'
import { usePermissions } from '@/shared/hooks/usePermissions'
import type { Lead } from '../types'

interface LeadsTableProps {
  leads: Lead[]
  total: number
  isLoading: boolean
  page: number
  limit: number
  onPageChange: (page: number) => void
  onEdit: (lead: Lead) => void
  onView: (lead: Lead) => void
  onDeleted: (id: number) => void
}

export function LeadsTable({
  leads,
  total,
  isLoading,
  page,
  limit,
  onPageChange,
  onEdit,
  onView,
  onDeleted,
}: LeadsTableProps) {
  const { isAdmin } = usePermissions()
  const [deleteTarget, setDeleteTarget] = useState<Lead | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const handleDelete = async () => {
    if (!deleteTarget) return
    setIsDeleting(true)
    try {
      await leadsService.deleteLead(deleteTarget.id)
      toast.success('Lead eliminado')
      onDeleted(deleteTarget.id)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsDeleting(false)
      setDeleteTarget(null)
    }
  }

  const columns: ColumnDef<Lead>[] = [
    {
      accessorKey: 'name',
      header: 'Nombre',
      cell: ({ row }) => (
        <div>
          <p className="font-medium text-foreground">{row.original.name}</p>
          <p className="text-xs text-muted-foreground">{row.original.phone}</p>
        </div>
      ),
    },
    {
      accessorKey: 'status',
      header: 'Temperatura',
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
    {
      accessorKey: 'lead_score',
      header: 'Score',
      cell: ({ row }) => <ScoreBadge score={row.original.lead_score} />,
    },
    {
      accessorKey: 'pipeline_stage',
      header: 'Etapa',
      cell: ({ row }) => <PipelineStageBadge stage={row.original.pipeline_stage} />,
    },
    ...(isAdmin
      ? [
          {
            id: 'calificacion',
            header: 'Calificación',
            cell: ({ row }: { row: { original: Lead } }) => (
              <QualificationBadge calificacion={row.original.lead_metadata?.calificacion} />
            ),
          } as ColumnDef<Lead>,
        ]
      : []),
    {
      accessorKey: 'last_contacted',
      header: 'Último contacto',
      cell: ({ row }) => (
        <span className="text-muted-foreground text-sm">
          {formatRelativeTime(row.original.last_contacted)}
        </span>
      ),
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="Acciones del lead">
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onView(row.original)}>
              <Eye className="mr-2 h-4 w-4" />
              Ver detalle
            </DropdownMenuItem>
            {isAdmin && (
              <>
                <DropdownMenuItem onClick={() => onEdit(row.original)}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Editar
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive"
                  onClick={() => setDeleteTarget(row.original)}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Eliminar
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ]

  return (
    <>
      <DataTable
        columns={columns}
        data={leads}
        isLoading={isLoading}
        total={total}
        page={page}
        limit={limit}
        onPageChange={onPageChange}
        emptyTitle="No hay leads"
        emptyDescription="Crea tu primer lead o importa desde un archivo CSV."
      />
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Eliminar lead"
        description={`¿Eliminar a "${deleteTarget?.name}"? Esta acción no se puede deshacer.`}
        confirmLabel="Eliminar"
        onConfirm={handleDelete}
        isLoading={isDeleting}
      />
    </>
  )
}
