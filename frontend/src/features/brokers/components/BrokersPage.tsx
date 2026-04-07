import { useState, useEffect } from 'react'
import { Plus, Trash2, ToggleLeft, ToggleRight, Loader2, MessageSquare } from 'lucide-react'
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
import { formatDate } from '@/shared/lib/utils'
import { cn } from '@/shared/lib/utils'
import { getErrorMessage } from '@/shared/types/api'
import { brokersService, type Broker } from '../services/brokers.service'
import { BrokerChatConfigDialog } from './BrokerChatConfigDialog'
import { plansApi } from '@/features/super-admin/services/plansApi'
import type { BrokerPlan } from '@/features/super-admin/types/plans.types'
import { useAuthStore } from '@/features/auth'
import { apiClient } from '@/shared/lib/api-client'
import { useNavigate } from 'react-router-dom'

export function BrokersPage() {
  const navigate = useNavigate()
  const { startImpersonation } = useAuthStore()
  const [brokers, setBrokers] = useState<Broker[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Broker | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [togglingId, setTogglingId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [creating, setCreating] = useState(false)

  // Plan assignment state
  const [plans, setPlans] = useState<BrokerPlan[]>([])
  const [planTarget, setPlanTarget] = useState<Broker | null>(null)
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null)
  const [assigningPlan, setAssigningPlan] = useState(false)

  // Chat config state
  const [chatConfigTarget, setChatConfigTarget] = useState<Broker | null>(null)

  const load = async () => {
    setIsLoading(true)
    try {
      const data = await brokersService.getAll()
      setBrokers(Array.isArray(data) ? data : [])
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    load()
    plansApi.list().then(setPlans).catch(() => {})
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      const broker = await brokersService.create({ name, email: email || undefined })
      setBrokers((prev) => [broker, ...prev])
      toast.success('Inmobiliaria creada')
      setShowCreate(false)
      setName('')
      setEmail('')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setCreating(false)
    }
  }

  const handleToggle = async (broker: Broker) => {
    setTogglingId(broker.id)
    try {
      const updated = await brokersService.update(broker.id, { is_active: !broker.is_active })
      setBrokers((prev) => prev.map((b) => (b.id === broker.id ? updated : b)))
      toast.success(updated.is_active ? 'Inmobiliaria activada' : 'Inmobiliaria desactivada')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setTogglingId(null)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setIsDeleting(true)
    try {
      await brokersService.delete(deleteTarget.id)
      setBrokers((prev) => prev.filter((b) => b.id !== deleteTarget.id))
      toast.success('Inmobiliaria eliminada')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsDeleting(false)
      setDeleteTarget(null)
    }
  }

  const handleImpersonate = async (broker: Broker) => {
    try {
      const res = await apiClient.post<{
        token: string
        broker_id: number
        broker_name: string
        expires_in: number
      }>(`/api/v1/admin/impersonate/${broker.id}`)
      startImpersonation(res.token, res.broker_name)
      toast.success(`Entrando como ${res.broker_name}`)
      navigate('/dashboard')
    } catch {
      toast.error('Error al iniciar impersonation')
    }
  }

  const handleAssignPlan = async () => {
    if (!planTarget) return
    setAssigningPlan(true)
    try {
      await plansApi.assignToBroker(planTarget.id, selectedPlanId)
      setBrokers((prev) => prev.map((b) => b.id === planTarget.id ? { ...b, plan_id: selectedPlanId } : b))
      toast.success('Plan asignado')
      setPlanTarget(null)
    } catch {
      toast.error('Error al asignar plan')
    } finally {
      setAssigningPlan(false)
    }
  }

  const columns: ColumnDef<Broker>[] = [
    {
      accessorKey: 'id',
      header: 'ID',
      cell: ({ row }) => <span className="text-muted-foreground tabular-nums">{row.original.id}</span>,
    },
    {
      accessorKey: 'name',
      header: 'Nombre',
      cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
    },
    {
      accessorKey: 'email',
      header: 'Email',
      cell: ({ row }) => <span className="text-sm text-muted-foreground">{row.original.email ?? '—'}</span>,
    },
    {
      accessorKey: 'is_active',
      header: 'Estado',
      cell: ({ row }) => (
        <span className={cn(
          'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
          row.original.is_active
            ? 'bg-emerald-100 text-emerald-700 border-emerald-200'
            : 'bg-slate-100 text-slate-600 border-slate-200'
        )}>
          {row.original.is_active ? 'Activa' : 'Inactiva'}
        </span>
      ),
    },
    {
      accessorKey: 'plan_id',
      header: 'Plan',
      cell: ({ row }) => {
        const plan = plans.find((p) => p.id === row.original.plan_id)
        return plan
          ? <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full font-medium">{plan.name}</span>
          : <span className="text-xs text-slate-400">Sin plan</span>
      },
    },
    {
      accessorKey: 'created_at',
      header: 'Creada',
      cell: ({ row }) => <span className="text-sm text-muted-foreground">{formatDate(row.original.created_at)}</span>,
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => {
        const b = row.original
        const loading = togglingId === b.id
        return (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-violet-600 hover:text-violet-700"
              onClick={() => handleImpersonate(b)}
              title="Ver el CRM como este broker"
            >
              Ver como
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-blue-600 hover:text-blue-700"
              onClick={() => {
                setPlanTarget(b)
                setSelectedPlanId(b.plan_id ?? null)
              }}
            >
              Plan
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-indigo-600 hover:text-indigo-700"
              onClick={() => setChatConfigTarget(b)}
              title="Configurar canales de chat"
            >
              <MessageSquare className="mr-1 h-3.5 w-3.5" />
              Canales
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className={cn('h-8 w-8', b.is_active ? 'text-amber-600' : 'text-emerald-600')}
              onClick={() => handleToggle(b)}
              disabled={loading}
              title={b.is_active ? 'Desactivar' : 'Activar'}
              aria-label={b.is_active ? 'Desactivar broker' : 'Activar broker'}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : b.is_active ? (
                <ToggleRight className="h-4 w-4" />
              ) : (
                <ToggleLeft className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-destructive hover:text-destructive"
              aria-label="Eliminar broker"
              onClick={() => setDeleteTarget(b)}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        )
      },
    },
  ]

  return (
    <div className="p-4 sm:p-8 space-y-6">
      <PageHeader
        title="Inmobiliarias"
        description={isLoading ? 'Cargando...' : `${brokers.length} inmobiliarias · ${brokers.filter(b => b.is_active).length} activas`}
        actions={
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Nueva Inmobiliaria
          </Button>
        }
      />

      <DataTable
        columns={columns}
        data={brokers}
        isLoading={isLoading}
        total={brokers.length}
        emptyTitle="Sin inmobiliarias"
        emptyDescription="Registra la primera inmobiliaria en el sistema"
      />

      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nueva Inmobiliaria</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label>Nombre</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Ej: Inmobiliaria Santiago Centro" />
            </div>
            <div className="space-y-2">
              <Label>Email (opcional)</Label>
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="contacto@empresa.cl" />
            </div>
            <DialogFooter>
              <Button variant="outline" type="button" onClick={() => setShowCreate(false)}>Cancelar</Button>
              <Button type="submit" disabled={creating}>
                {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Crear
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
        title="Eliminar inmobiliaria"
        description={`¿Eliminar "${deleteTarget?.name}"? Se eliminarán todos sus datos.`}
        confirmLabel="Eliminar"
        onConfirm={handleDelete}
        isLoading={isDeleting}
      />

      {/* Assign plan dialog */}
      <Dialog open={!!planTarget} onOpenChange={(o) => !o && setPlanTarget(null)}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Asignar plan — {planTarget?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Label className="text-xs">Plan comercial</Label>
            <select
              className="w-full text-sm border rounded-lg px-3 py-2 bg-white text-slate-700"
              value={selectedPlanId ?? ''}
              onChange={(e) => setSelectedPlanId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Sin plan (ilimitado)</option>
              {plans.filter((p) => p.is_active).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPlanTarget(null)}>Cancelar</Button>
            <Button onClick={handleAssignPlan} disabled={assigningPlan}>
              {assigningPlan ? 'Guardando...' : 'Asignar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <BrokerChatConfigDialog
        broker={chatConfigTarget}
        onClose={() => setChatConfigTarget(null)}
      />
    </div>
  )
}
