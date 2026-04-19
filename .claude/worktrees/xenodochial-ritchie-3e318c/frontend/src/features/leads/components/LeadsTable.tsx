import { useState } from 'react'
import { type ColumnDef } from '@tanstack/react-table'
import { MoreHorizontal, Pencil, Trash2, Eye, Columns3 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuCheckboxItem,
  DropdownMenuLabel,
} from '@/shared/components/ui/dropdown-menu'
import { DataTable } from '@/shared/components/common/DataTable'
import { StatusBadge } from '@/shared/components/common/StatusBadge'
import { ScoreBadge } from '@/shared/components/common/ScoreBadge'
import { PipelineStageBadge } from '@/shared/components/common/PipelineStageBadge'
import { QualificationBadge } from '@/shared/components/common/QualificationBadge'
import { ConfirmDialog } from '@/shared/components/common/ConfirmDialog'
import { formatRelativeTime, formatDate, formatCurrency } from '@/shared/lib/utils'
import { DICOM_CONFIG } from '@/shared/lib/constants'
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

/** Columns that can be toggled by the user. Maps id → label. */
const TOGGLEABLE_COLUMNS: Record<string, string> = {
  email: 'Email',
  monthly_income: 'Sueldo',
  dicom: 'DICOM',
  created_at: 'Fecha creación',
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
  const [hiddenCols, setHiddenCols] = useState<Set<string>>(new Set())

  const toggleCol = (id: string) => {
    setHiddenCols((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

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

  const allColumns: ColumnDef<Lead>[] = [
    {
      accessorKey: 'name',
      header: 'Nombre',
      cell: ({ row }) => (
        <p className="font-medium text-foreground">{row.original.name ?? '—'}</p>
      ),
    },
    {
      accessorKey: 'phone',
      header: 'Teléfono',
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground tabular-nums">{row.original.phone}</span>
      ),
    },
    {
      id: 'email',
      header: 'Email',
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground truncate max-w-[180px] block">
          {row.original.email ?? '—'}
        </span>
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
      ? ([
          {
            id: 'calificacion',
            header: 'Calificación',
            cell: ({ row }: { row: { original: Lead } }) => (
              <QualificationBadge calificacion={row.original.lead_metadata?.calificacion} />
            ),
          },
          {
            id: 'monthly_income',
            header: 'Sueldo',
            cell: ({ row }: { row: { original: Lead } }) => {
              const income = row.original.lead_metadata?.monthly_income
              return (
                <span className="text-sm text-foreground tabular-nums">
                  {income ? formatCurrency(Number(income)) : '—'}
                </span>
              )
            },
          },
          {
            id: 'dicom',
            header: 'DICOM',
            cell: ({ row }: { row: { original: Lead } }) => {
              const status = row.original.lead_metadata?.dicom_status
              if (!status) return <span className="text-muted-foreground text-sm">—</span>
              const cfg = DICOM_CONFIG[status]
              return (
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${
                  status === 'clean'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : status === 'has_debt'
                    ? 'bg-rose-50 text-rose-600 border-rose-200'
                    : 'bg-slate-100 text-slate-600 border-slate-200'
                }`}>
                  {cfg?.label ?? status}
                </span>
              )
            },
          },
        ] as ColumnDef<Lead>[])
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
      id: 'created_at',
      header: 'Creado',
      cell: ({ row }) => (
        <span className="text-muted-foreground text-sm">{formatDate(row.original.created_at)}</span>
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

  const visibleColumns = allColumns.filter(
    (col) => !(col.id && hiddenCols.has(col.id))
  )

  return (
    <>
      {/* Column visibility toggle */}
      <div className="flex justify-end mb-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
              <Columns3 className="h-3.5 w-3.5" />
              Columnas
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-44">
            <DropdownMenuLabel className="text-xs text-muted-foreground">
              Mostrar columnas
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {Object.entries(TOGGLEABLE_COLUMNS)
              .filter(([id]) => {
                // Only show admin-only columns in selector for admins
                if (['monthly_income', 'dicom'].includes(id) && !isAdmin) return false
                return true
              })
              .map(([id, label]) => (
                <DropdownMenuCheckboxItem
                  key={id}
                  checked={!hiddenCols.has(id)}
                  onCheckedChange={() => toggleCol(id)}
                >
                  {label}
                </DropdownMenuCheckboxItem>
              ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <DataTable
        columns={visibleColumns}
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


