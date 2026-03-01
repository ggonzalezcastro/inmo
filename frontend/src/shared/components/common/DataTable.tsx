import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/shared/lib/utils'
import { Button } from '@/shared/components/ui/button'
import { LoadingSpinner } from './LoadingSpinner'
import { EmptyState } from './EmptyState'

interface DataTableProps<TData> {
  columns: ColumnDef<TData>[]
  data: TData[]
  isLoading?: boolean
  total?: number
  page?: number
  limit?: number
  onPageChange?: (page: number) => void
  emptyTitle?: string
  emptyDescription?: string
  className?: string
}

export function DataTable<TData>({
  columns,
  data,
  isLoading = false,
  total = 0,
  page = 1,
  limit = 20,
  onPageChange,
  emptyTitle = 'Sin resultados',
  emptyDescription,
  className,
}: DataTableProps<TData>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: Math.ceil(total / limit),
  })

  const totalPages = Math.ceil(total / limit)
  const showPagination = onPageChange && totalPages > 1

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      <div className="rounded-md border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-4 py-3 text-left font-medium text-muted-foreground whitespace-nowrap"
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-border bg-background">
              {isLoading ? (
                <tr>
                  <td colSpan={columns.length} className="py-16 text-center">
                    <LoadingSpinner className="mx-auto" />
                  </td>
                </tr>
              ) : table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td colSpan={columns.length}>
                    <EmptyState title={emptyTitle} description={emptyDescription} />
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    className="hover:bg-muted/30 transition-colors"
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-4 py-3 whitespace-nowrap">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {showPagination && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Mostrando {Math.min((page - 1) * limit + 1, total)}–{Math.min(page * limit, total)} de {total}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              aria-label="Página anterior"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="px-3 py-1 font-medium">
              {page} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              aria-label="Página siguiente"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
