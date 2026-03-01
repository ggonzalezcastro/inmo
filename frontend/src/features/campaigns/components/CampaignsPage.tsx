import { useState, useEffect } from 'react'
import { Plus, Trash2, Play, ChevronDown, ChevronUp, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { Badge } from '@/shared/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { ConfirmDialog } from '@/shared/components/common/ConfirmDialog'
import { EmptyState } from '@/shared/components/common/EmptyState'
import { LoadingSpinner } from '@/shared/components/common/LoadingSpinner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/shared/components/ui/dialog'
import { getErrorMessage } from '@/shared/types/api'
import { campaignsService, type Campaign } from '../services/campaigns.service'

function StatusBadge({ status }: { status: Campaign['status'] }) {
  const map = {
    active: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    inactive: 'bg-slate-100 text-slate-600 border-slate-200',
    draft: 'bg-amber-100 text-amber-700 border-amber-200',
  }
  const labels = { active: 'Activa', inactive: 'Inactiva', draft: 'Borrador' }
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${map[status]}`}>
      {labels[status]}
    </span>
  )
}

export function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Campaign | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [applyLeadId, setApplyLeadId] = useState('')
  const [applying, setApplying] = useState<number | null>(null)

  const load = async () => {
    setIsLoading(true)
    try {
      const data = await campaignsService.getAll()
      setCampaigns(Array.isArray(data) ? data : [])
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      const c = await campaignsService.create({ name: newName, description: newDesc || undefined })
      setCampaigns((prev) => [c, ...prev])
      toast.success('Campaña creada')
      setShowCreate(false)
      setNewName('')
      setNewDesc('')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setIsDeleting(true)
    try {
      await campaignsService.delete(deleteTarget.id)
      setCampaigns((prev) => prev.filter((c) => c.id !== deleteTarget.id))
      toast.success('Campaña eliminada')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setIsDeleting(false)
      setDeleteTarget(null)
    }
  }

  const handleApply = async (campaignId: number) => {
    const id = parseInt(applyLeadId)
    if (!id) return
    setApplying(campaignId)
    try {
      await campaignsService.applyToLead(campaignId, id)
      toast.success(`Campaña aplicada al lead #${id}`)
      setApplyLeadId('')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setApplying(null)
    }
  }

  return (
    <div className="p-8 space-y-6">
      <PageHeader
        title="Campañas"
        description="Automatización multicanal de contacto"
        actions={
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Nueva Campaña
          </Button>
        }
      />

      {isLoading ? (
        <div className="flex justify-center py-16"><LoadingSpinner size="lg" /></div>
      ) : campaigns.length === 0 ? (
        <EmptyState
          title="Sin campañas"
          description="Crea tu primera campaña de automatización"
          action={{ label: 'Crear campaña', onClick: () => setShowCreate(true) }}
        />
      ) : (
        <div className="space-y-3">
          {campaigns.map((campaign) => (
            <Card key={campaign.id}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <CardTitle className="text-base">{campaign.name}</CardTitle>
                    <StatusBadge status={campaign.status} />
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Eliminar campaña"
                      className="h-8 w-8 text-destructive hover:text-destructive"
                      onClick={() => setDeleteTarget(campaign)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={expanded === campaign.id ? 'Colapsar campaña' : 'Expandir campaña'}
                      className="h-8 w-8"
                      onClick={() => setExpanded(expanded === campaign.id ? null : campaign.id)}
                    >
                      {expanded === campaign.id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
                {campaign.description && (
                  <p className="text-sm text-muted-foreground mt-1">{campaign.description}</p>
                )}
              </CardHeader>

              {expanded === campaign.id && (
                <CardContent className="pt-0 border-t border-border space-y-4">
                  {/* Stats */}
                  {campaign.stats && (
                    <div className="flex gap-6 text-sm">
                      <div>
                        <p className="text-muted-foreground">Enviados</p>
                        <p className="font-semibold">{campaign.stats.total_sent}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Fallidos</p>
                        <p className="font-semibold text-rose-600">{campaign.stats.total_failed}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Éxito</p>
                        <p className="font-semibold text-emerald-600">{campaign.stats.success_rate}%</p>
                      </div>
                    </div>
                  )}

                  {/* Apply to lead */}
                  <div className="flex items-center gap-2">
                    <Input
                      type="number"
                      placeholder="ID del lead"
                      value={applyLeadId}
                      onChange={(e) => setApplyLeadId(e.target.value)}
                      className="w-36 h-8 text-sm"
                    />
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleApply(campaign.id)}
                      disabled={!applyLeadId || applying === campaign.id}
                    >
                      {applying === campaign.id ? (
                        <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Play className="mr-2 h-3.5 w-3.5" />
                      )}
                      Aplicar a lead
                    </Button>
                  </div>

                  {/* Steps */}
                  {campaign.steps && campaign.steps.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-muted-foreground uppercase mb-2">
                        Pasos ({campaign.steps.length})
                      </p>
                      <div className="space-y-2">
                        {campaign.steps.map((step) => (
                          <div
                            key={step.id}
                            className="flex items-center gap-3 text-sm p-2 rounded bg-muted/40"
                          >
                            <Badge variant="secondary" className="shrink-0">{step.order}</Badge>
                            <span className="flex-1">{step.action}</span>
                            <span className="text-muted-foreground text-xs shrink-0">
                              {step.delay_minutes}m delay
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Nueva Campaña</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label>Nombre</Label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} required placeholder="Ej: Seguimiento leads fríos" />
            </div>
            <div className="space-y-2">
              <Label>Descripción (opcional)</Label>
              <Input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="Descripción breve" />
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
        title="Eliminar campaña"
        description={`¿Eliminar "${deleteTarget?.name}"? Los pasos activos serán cancelados.`}
        confirmLabel="Eliminar"
        onConfirm={handleDelete}
        isLoading={isDeleting}
      />
    </div>
  )
}
