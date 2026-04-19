import { useState, useEffect } from 'react'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { type ColumnDef } from '@tanstack/react-table'
import { Button } from '@/shared/components/ui/button'
import { Badge } from '@/shared/components/ui/badge'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { DataTable } from '@/shared/components/common/DataTable'
import { ConfirmDialog } from '@/shared/components/common/ConfirmDialog'
import { CHANNEL_LABELS, AGENT_TYPE_LABELS } from '@/shared/lib/constants'
import { getErrorMessage } from '@/shared/types/api'
import { templatesService, type Template } from '../services/templates.service'
import { TemplateEditorDialog } from './TemplateEditorDialog'

export function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [editTarget, setEditTarget] = useState<Template | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Template | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const load = async () => {
    setIsLoading(true)
    try {
      const data = await templatesService.getAll()
      setTemplates(Array.isArray(data) ? data : [])
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async () => {
    if (!deleteTarget) return
    setIsDeleting(true)
    try {
      await templatesService.delete(deleteTarget.id)
      setTemplates((prev) => prev.filter((t) => t.id !== deleteTarget.id))
      toast.success('Template eliminado')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsDeleting(false)
      setDeleteTarget(null)
    }
  }

  const columns: ColumnDef<Template>[] = [
    {
      accessorKey: 'name',
      header: 'Nombre',
      cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
    },
    {
      accessorKey: 'channel',
      header: 'Canal',
      cell: ({ row }) => (
        <Badge variant="secondary">{CHANNEL_LABELS[row.original.channel] ?? row.original.channel}</Badge>
      ),
    },
    {
      accessorKey: 'agent_type',
      header: 'Agente',
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">
          {AGENT_TYPE_LABELS[row.original.agent_type] ?? row.original.agent_type}
        </span>
      ),
    },
    {
      accessorKey: 'content',
      header: 'Vista previa',
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground truncate max-w-[240px] block">
          {row.original.content.slice(0, 80)}…
        </span>
      ),
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="Editar plantilla" onClick={() => setEditTarget(row.original)}>
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Eliminar plantilla"
            className="h-8 w-8 text-destructive hover:text-destructive"
            onClick={() => setDeleteTarget(row.original)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ]

  const handleSuccess = (t: Template) => {
    setTemplates((prev) => {
      const idx = prev.findIndex((x) => x.id === t.id)
      if (idx >= 0) return prev.map((x) => (x.id === t.id ? t : x))
      return [t, ...prev]
    })
  }

  return (
    <div className="p-8 space-y-6">
      <PageHeader
        title="Templates"
        description="Mensajes reutilizables para el agente IA"
        actions={
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Nuevo Template
          </Button>
        }
      />

      <DataTable
        columns={columns}
        data={templates}
        isLoading={isLoading}
        total={templates.length}
        emptyTitle="Sin templates"
        emptyDescription="Crea tu primer template de mensaje"
      />

      <TemplateEditorDialog
        open={showCreate}
        onOpenChange={setShowCreate}
        onSuccess={handleSuccess}
      />
      <TemplateEditorDialog
        open={!!editTarget}
        onOpenChange={(open) => !open && setEditTarget(null)}
        template={editTarget}
        onSuccess={handleSuccess}
      />
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Eliminar template"
        description={`¿Eliminar "${deleteTarget?.name}"?`}
        confirmLabel="Eliminar"
        onConfirm={handleDelete}
        isLoading={isDeleting}
      />
    </div>
  )
}
