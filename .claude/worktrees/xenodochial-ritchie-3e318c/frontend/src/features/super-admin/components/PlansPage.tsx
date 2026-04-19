import { useEffect, useState } from 'react'
import { Plus, Trash2, Pencil } from 'lucide-react'
import { toast } from 'sonner'
import { type ColumnDef } from '@tanstack/react-table'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { DataTable } from '@/shared/components/common/DataTable'
import { ConfirmDialog } from '@/shared/components/common/ConfirmDialog'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/shared/components/ui/dialog'
import { plansApi } from '../services/plansApi'
import type { BrokerPlan, PlanCreate } from '../types/plans.types'

function limitLabel(val: number | null) {
  if (val === null) return <span className="text-slate-400 text-xs">Ilimitado</span>
  return <span className="text-xs font-medium">{val.toLocaleString()}</span>
}

const EMPTY_FORM: PlanCreate = {
  name: '',
  description: '',
  max_leads: null,
  max_users: null,
  max_messages_per_month: null,
  max_llm_cost_per_month: null,
  is_default: false,
}

export function PlansPage() {
  const [plans, setPlans] = useState<BrokerPlan[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editTarget, setEditTarget] = useState<BrokerPlan | null>(null)
  const [deactivateTarget, setDeactivateTarget] = useState<BrokerPlan | null>(null)
  const [form, setForm] = useState<PlanCreate>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setIsLoading(true)
    try {
      const data = await plansApi.list()
      setPlans(data)
    } catch {
      toast.error('Error al cargar planes')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const openCreate = () => {
    setEditTarget(null)
    setForm(EMPTY_FORM)
    setShowForm(true)
  }

  const openEdit = (plan: BrokerPlan) => {
    setEditTarget(plan)
    setForm({
      name: plan.name,
      description: plan.description ?? '',
      max_leads: plan.max_leads,
      max_users: plan.max_users,
      max_messages_per_month: plan.max_messages_per_month,
      max_llm_cost_per_month: plan.max_llm_cost_per_month,
      is_default: plan.is_default,
    })
    setShowForm(true)
  }

  const handleSave = async () => {
    if (!form.name.trim()) return toast.error('El nombre es obligatorio')
    setSaving(true)
    try {
      if (editTarget) {
        await plansApi.update(editTarget.id, form)
        toast.success('Plan actualizado')
      } else {
        await plansApi.create(form)
        toast.success('Plan creado')
      }
      setShowForm(false)
      await load()
    } catch {
      toast.error('Error al guardar plan')
    } finally {
      setSaving(false)
    }
  }

  const handleDeactivate = async () => {
    if (!deactivateTarget) return
    try {
      await plansApi.deactivate(deactivateTarget.id)
      toast.success('Plan desactivado')
      setDeactivateTarget(null)
      await load()
    } catch {
      toast.error('Error al desactivar plan')
    }
  }

  const numInput = (
    field: keyof PlanCreate,
    label: string,
    placeholder = 'Vacío = ilimitado'
  ) => (
    <div className="space-y-1">
      <Label className="text-xs">{label}</Label>
      <Input
        type="number"
        min={0}
        placeholder={placeholder}
        value={(form[field] as number | null) ?? ''}
        onChange={(e) => setForm((f) => ({
          ...f,
          [field]: e.target.value === '' ? null : Number(e.target.value),
        }))}
        className="h-8 text-sm"
      />
    </div>
  )

  const columns: ColumnDef<BrokerPlan>[] = [
    {
      accessorKey: 'name',
      header: 'Nombre',
      cell: ({ row }) => (
        <div>
          <span className="text-sm font-medium text-slate-800">{row.original.name}</span>
          {row.original.is_default && (
            <span className="ml-2 text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full font-medium">
              Default
            </span>
          )}
          {!row.original.is_active && (
            <span className="ml-2 text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded-full">
              Inactivo
            </span>
          )}
        </div>
      ),
    },
    { accessorKey: 'max_leads', header: 'Leads', cell: ({ getValue }) => limitLabel(getValue() as number | null) },
    { accessorKey: 'max_users', header: 'Usuarios', cell: ({ getValue }) => limitLabel(getValue() as number | null) },
    { accessorKey: 'max_messages_per_month', header: 'Mensajes/mes', cell: ({ getValue }) => limitLabel(getValue() as number | null) },
    {
      accessorKey: 'max_llm_cost_per_month',
      header: 'Costo max/mes',
      cell: ({ getValue }) => {
        const v = getValue() as number | null
        return v === null
          ? <span className="text-slate-400 text-xs">Ilimitado</span>
          : <span className="text-xs font-medium">${v.toFixed(0)}</span>
      },
    },
    {
      id: 'actions',
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => openEdit(row.original)}>
            <Pencil size={12} />
          </Button>
          {row.original.is_active && (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-red-500 hover:text-red-600"
              onClick={() => setDeactivateTarget(row.original)}
            >
              <Trash2 size={12} />
            </Button>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <PageHeader title="Planes" description="Gestiona los planes comerciales de los brokers" />
        <Button size="sm" onClick={openCreate}>
          <Plus size={14} className="mr-1" />
          Nuevo plan
        </Button>
      </div>

      <DataTable columns={columns} data={plans} isLoading={isLoading} />

      {/* Create / Edit dialog */}
      <Dialog open={showForm} onOpenChange={(o) => !o && setShowForm(false)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editTarget ? 'Editar plan' : 'Nuevo plan'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label className="text-xs">Nombre *</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="h-8 text-sm"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Descripción</Label>
              <Input
                value={form.description ?? ''}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                className="h-8 text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              {numInput('max_leads', 'Máx. leads')}
              {numInput('max_users', 'Máx. usuarios')}
              {numInput('max_messages_per_month', 'Máx. mensajes/mes')}
              {numInput('max_llm_cost_per_month', 'Costo max USD/mes')}
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_default}
                onChange={(e) => setForm((f) => ({ ...f, is_default: e.target.checked }))}
                className="rounded"
              />
              Plan por defecto para nuevos brokers
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowForm(false)}>Cancelar</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? 'Guardando...' : 'Guardar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deactivateTarget}
        onOpenChange={(o) => !o && setDeactivateTarget(null)}
        title={`Desactivar plan "${deactivateTarget?.name}"`}
        description="Los brokers con este plan seguirán funcionando, pero no podrán asignarlo a nuevos brokers."
        onConfirm={handleDeactivate}
      />
    </div>
  )
}
