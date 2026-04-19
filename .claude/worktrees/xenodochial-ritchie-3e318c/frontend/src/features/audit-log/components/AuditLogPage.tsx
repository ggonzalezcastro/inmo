import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { type ColumnDef } from '@tanstack/react-table'
import { Button } from '@/shared/components/ui/button'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { DataTable } from '@/shared/components/common/DataTable'
import { AuditLogDetailDialog } from './AuditLogDetailDialog'
import { useAuditLogStore } from '../store/auditLogStore'
import type { AuditLogEntry } from '../types/auditLog.types'
import { formatDate } from '@/shared/lib/utils'

const ACTION_OPTIONS = ['login', 'create', 'update', 'delete', 'impersonation_start', 'impersonation_end']
const RESOURCE_OPTIONS = ['broker', 'user', 'lead', 'config', 'campaign']

export function AuditLogPage() {
  const { entries, total, isLoading, filters, setFilters, fetchEntries } = useAuditLogStore()
  const [detailEntry, setDetailEntry] = useState<AuditLogEntry | null>(null)

  useEffect(() => {
    fetchEntries()
  }, [])

  const columns: ColumnDef<AuditLogEntry>[] = [
    {
      accessorKey: 'timestamp',
      header: 'Fecha',
      cell: ({ getValue }) => (
        <span className="text-xs text-slate-500">{formatDate(String(getValue()))}</span>
      ),
    },
    {
      accessorKey: 'user_email',
      header: 'Usuario',
      cell: ({ getValue }) => (
        <span className="text-xs text-slate-700">{String(getValue() ?? '—')}</span>
      ),
    },
    {
      accessorKey: 'action',
      header: 'Acción',
      cell: ({ getValue }) => {
        const val = String(getValue())
        const colorMap: Record<string, string> = {
          login: 'bg-blue-100 text-blue-700',
          create: 'bg-green-100 text-green-700',
          update: 'bg-yellow-100 text-yellow-700',
          delete: 'bg-red-100 text-red-700',
          impersonation_start: 'bg-violet-100 text-violet-700',
          impersonation_end: 'bg-slate-100 text-slate-600',
        }
        const cls = colorMap[val] ?? 'bg-slate-100 text-slate-600'
        return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>{val}</span>
      },
    },
    {
      accessorKey: 'resource_type',
      header: 'Recurso',
      cell: ({ row }) => (
        <span className="text-xs text-slate-600">
          {row.original.resource_type}:{row.original.resource_id}
        </span>
      ),
    },
    {
      accessorKey: 'broker_id',
      header: 'Broker',
      cell: ({ getValue }) => (
        <span className="text-xs text-slate-500">{String(getValue() ?? '—')}</span>
      ),
    },
    {
      accessorKey: 'ip_address',
      header: 'IP',
      cell: ({ getValue }) => (
        <span className="text-xs text-slate-400 font-mono">{String(getValue() ?? '—')}</span>
      ),
    },
    {
      id: 'actions',
      cell: ({ row }) => (
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2 text-xs"
          onClick={() => setDetailEntry(row.original)}
        >
          Ver
        </Button>
      ),
    },
  ]

  const page = filters.page ?? 1
  const limit = 50

  return (
    <div className="space-y-4">
      <PageHeader title="Audit Log" description={`${total} entradas`} />

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <select
          className="text-sm border rounded-lg px-3 py-1.5 bg-white text-slate-700"
          value={filters.action ?? ''}
          onChange={(e) => setFilters({ action: e.target.value || undefined })}
        >
          <option value="">Todas las acciones</option>
          {ACTION_OPTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>

        <select
          className="text-sm border rounded-lg px-3 py-1.5 bg-white text-slate-700"
          value={filters.resource_type ?? ''}
          onChange={(e) => setFilters({ resource_type: e.target.value || undefined })}
        >
          <option value="">Todos los recursos</option>
          {RESOURCE_OPTIONS.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>

        <input
          type="date"
          className="text-sm border rounded-lg px-3 py-1.5 bg-white text-slate-700"
          value={filters.from_date ?? ''}
          onChange={(e) => setFilters({ from_date: e.target.value || undefined })}
          placeholder="Desde"
        />
        <input
          type="date"
          className="text-sm border rounded-lg px-3 py-1.5 bg-white text-slate-700"
          value={filters.to_date ?? ''}
          onChange={(e) => setFilters({ to_date: e.target.value || undefined })}
          placeholder="Hasta"
        />
      </div>

      <DataTable columns={columns} data={entries} isLoading={isLoading} />

      {/* Pagination */}
      {total > limit && (
        <div className="flex items-center justify-between text-sm text-slate-500">
          <span>
            Página {page} · {total} entradas
          </span>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="ghost"
              disabled={page <= 1}
              onClick={() => setFilters({ page: page - 1 })}
            >
              <ChevronLeft size={14} />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={page * limit >= total}
              onClick={() => setFilters({ page: page + 1 })}
            >
              <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      )}

      <AuditLogDetailDialog entry={detailEntry} onClose={() => setDetailEntry(null)} />
    </div>
  )
}
