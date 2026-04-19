import { useEffect, useRef, useState } from 'react'
import { RefreshCw, RotateCcw, Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { type ColumnDef } from '@tanstack/react-table'
import { Button } from '@/shared/components/ui/button'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { DataTable } from '@/shared/components/common/DataTable'
import { ConfirmDialog } from '@/shared/components/common/ConfirmDialog'
import { DLQDetailDialog } from './DLQDetailDialog'
import { useDLQStore } from '../store/dlqStore'
import type { DLQEntry } from '../types/dlq.types'
import { formatDate } from '@/shared/lib/utils'

const LIMIT = 50
const REFRESH_MS = 30_000

export function DLQPage() {
  const { entries, total, offset, isLoading, fetchEntries, retryEntry, discardEntry, bulkRetry, bulkDiscard } =
    useDLQStore()
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [detailEntry, setDetailEntry] = useState<DLQEntry | null>(null)
  const [confirmBulk, setConfirmBulk] = useState<'retry' | 'discard' | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    fetchEntries(0)
    intervalRef.current = setInterval(() => fetchEntries(offset), REFRESH_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  const columns: ColumnDef<DLQEntry>[] = [
    {
      id: 'select',
      header: () => (
        <input
          type="checkbox"
          checked={selectedIds.length === entries.length && entries.length > 0}
          onChange={(e) => setSelectedIds(e.target.checked ? entries.map((r) => r.id) : [])}
          className="rounded"
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={selectedIds.includes(row.original.id)}
          onChange={(e) => {
            setSelectedIds((prev) =>
              e.target.checked ? [...prev, row.original.id] : prev.filter((id) => id !== row.original.id)
            )
          }}
          className="rounded"
        />
      ),
    },
    {
      accessorKey: 'task_name',
      header: 'Tarea',
      cell: ({ row }) => (
        <button
          className="font-mono text-xs text-blue-600 hover:underline text-left"
          onClick={() => setDetailEntry(row.original)}
        >
          {row.original.task_name}
        </button>
      ),
    },
    {
      accessorKey: 'exception',
      header: 'Error',
      cell: ({ getValue }) => (
        <span className="text-xs text-red-600 font-mono truncate max-w-[300px] block">
          {String(getValue()).slice(0, 120)}
        </span>
      ),
    },
    {
      accessorKey: 'retries',
      header: 'Reintentos',
      cell: ({ getValue }) => (
        <span className="text-xs text-slate-600">{String(getValue())}</span>
      ),
    },
    {
      accessorKey: 'failed_at',
      header: 'Fallida',
      cell: ({ getValue }) => (
        <span className="text-xs text-slate-500">{formatDate(String(getValue()))}</span>
      ),
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs text-emerald-600 hover:text-emerald-700"
            onClick={() => retryEntry(row.original.id)}
          >
            <RotateCcw size={12} className="mr-1" />
            Retry
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs text-red-500 hover:text-red-600"
            onClick={() => discardEntry(row.original.id)}
          >
            <Trash2 size={12} className="mr-1" />
            Descartar
          </Button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader
          title="Dead Letter Queue"
          description={`${total} tareas fallidas`}
        />
        <div className="flex items-center gap-2">
          {selectedIds.length > 0 && (
            <>
              <Button
                size="sm"
                variant="outline"
                className="text-emerald-600 border-emerald-200 hover:bg-emerald-50"
                onClick={() => setConfirmBulk('retry')}
              >
                <RotateCcw size={12} className="mr-1" />
                Retry ({selectedIds.length})
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="text-red-500 border-red-200 hover:bg-red-50"
                onClick={() => setConfirmBulk('discard')}
              >
                <Trash2 size={12} className="mr-1" />
                Descartar ({selectedIds.length})
              </Button>
            </>
          )}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => fetchEntries(offset)}
            disabled={isLoading}
          >
            <RefreshCw size={12} className={isLoading ? 'animate-spin' : ''} />
          </Button>
        </div>
      </div>

      <DataTable columns={columns} data={entries} isLoading={isLoading} />

      {/* Pagination */}
      {total > LIMIT && (
        <div className="flex items-center justify-between text-sm text-slate-500">
          <span>
            Mostrando {offset + 1}–{Math.min(offset + LIMIT, total)} de {total}
          </span>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="ghost"
              disabled={offset === 0}
              onClick={() => fetchEntries(Math.max(0, offset - LIMIT))}
            >
              <ChevronLeft size={14} />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={offset + LIMIT >= total}
              onClick={() => fetchEntries(offset + LIMIT)}
            >
              <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      )}

      <DLQDetailDialog entry={detailEntry} onClose={() => setDetailEntry(null)} />

      <ConfirmDialog
        open={confirmBulk === 'retry'}
        onOpenChange={(open) => !open && setConfirmBulk(null)}
        title={`Reintentar ${selectedIds.length} tareas`}
        description="¿Seguro que deseas re-encolar las tareas seleccionadas?"
        onConfirm={async () => {
          await bulkRetry(selectedIds)
          setSelectedIds([])
          setConfirmBulk(null)
        }}
      />
      <ConfirmDialog
        open={confirmBulk === 'discard'}
        onOpenChange={(open) => !open && setConfirmBulk(null)}
        title={`Descartar ${selectedIds.length} tareas`}
        description="Esta acción es irreversible. ¿Confirmas el descarte?"
        onConfirm={async () => {
          await bulkDiscard(selectedIds)
          setSelectedIds([])
          setConfirmBulk(null)
        }}
      />
    </div>
  )
}
