import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, Plus, Loader2, ArrowRight, CheckCircle2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { useDealsStore } from '../store/dealsStore'
import { usePermissions } from '@/shared/hooks/usePermissions'
import { propertiesService } from '@/features/properties/services/properties.service'
import { formatDate } from '@/shared/lib/utils'
import { getErrorMessage } from '@/shared/types/api'
import type { Deal, DealStage, DeliveryType } from '../types'
import type { Property } from '@/features/properties/types'

interface DealPanelProps {
  leadId: number
  brokerLeadConfig?: { ai_can_upload_deal_files?: boolean }
}

// ── Stage config ─────────────────────────────────────────────────────────────

const STAGE_ORDER: DealStage[] = [
  'draft',
  'reserva',
  'docs_pendientes',
  'en_aprobacion_bancaria',
  'promesa_redaccion',
  'promesa_firmada',
  'escritura_firmada',
]

const TERMINAL_STAGES: DealStage[] = ['escritura_firmada', 'cancelado']

const STAGE_LABELS: Record<DealStage, string> = {
  draft: 'Borrador',
  reserva: 'Reserva',
  docs_pendientes: 'Docs. pendientes',
  en_aprobacion_bancaria: 'Aprobación bancaria',
  promesa_redaccion: 'Promesa (redacción)',
  promesa_firmada: 'Promesa firmada',
  escritura_firmada: 'Escritura firmada',
  cancelado: 'Cancelado',
}

const STAGE_BADGE_CLASSES: Record<DealStage, string> = {
  draft: 'bg-gray-100 text-gray-600 border-gray-200',
  reserva: 'bg-blue-100 text-blue-700 border-blue-200',
  docs_pendientes: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  en_aprobacion_bancaria: 'bg-orange-100 text-orange-700 border-orange-200',
  promesa_redaccion: 'bg-purple-100 text-purple-700 border-purple-200',
  promesa_firmada: 'bg-purple-100 text-purple-700 border-purple-200',
  escritura_firmada: 'bg-green-100 text-green-700 border-green-200',
  cancelado: 'bg-red-100 text-red-600 border-red-200',
}

const DELIVERY_TYPE_LABELS: Record<DeliveryType, string> = {
  inmediata: 'Inmediata',
  futura: 'Futura',
  desconocida: 'Desconocida',
}

function getNextStage(current: DealStage): DealStage | null {
  const idx = STAGE_ORDER.indexOf(current)
  if (idx === -1 || idx === STAGE_ORDER.length - 1) return null
  return STAGE_ORDER[idx + 1]
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StageBadge({ stage }: { stage: DealStage }) {
  return (
    <span
      className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full border ${STAGE_BADGE_CLASSES[stage]}`}
    >
      {STAGE_LABELS[stage]}
    </span>
  )
}

function StageTimeline({ stage }: { stage: DealStage }) {
  const isCancelled = stage === 'cancelado'

  return (
    <div className="mt-2 mb-1">
      <div className="flex items-center gap-0.5 flex-wrap">
        {STAGE_ORDER.map((s, i) => {
          const currentIdx = STAGE_ORDER.indexOf(isCancelled ? 'draft' : stage)
          const isPast = i < currentIdx
          const isCurrent = s === stage && !isCancelled
          const isFuture = i > currentIdx

          return (
            <div key={s} className="flex items-center gap-0.5">
              <div
                className={`h-2 w-2 rounded-full shrink-0 ${
                  isCurrent
                    ? 'bg-blue-500'
                    : isPast
                    ? 'bg-green-400'
                    : 'bg-gray-200'
                } ${isFuture ? 'opacity-50' : ''}`}
                title={STAGE_LABELS[s]}
              />
              {i < STAGE_ORDER.length - 1 && (
                <div
                  className={`h-0.5 w-3 ${isPast ? 'bg-green-400' : 'bg-gray-200'}`}
                />
              )}
            </div>
          )
        })}
      </div>
      <p className="text-[10px] text-muted-foreground mt-1">
        {isCancelled ? 'Cancelado' : STAGE_LABELS[stage]}
      </p>
    </div>
  )
}

interface DealCardProps {
  deal: Deal
  canAdvance: boolean
}

function DealCard({ deal, canAdvance }: DealCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [advancing, setAdvancing] = useState(false)
  const { transitionDeal } = useDealsStore()

  const nextStage = getNextStage(deal.stage)
  const isTerminal = TERMINAL_STAGES.includes(deal.stage)

  const handleAdvance = async () => {
    if (!nextStage) return
    setAdvancing(true)
    try {
      await transitionDeal(deal.id, { to_stage: nextStage })
      toast.success(`Deal avanzado a "${STAGE_LABELS[nextStage]}"`)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setAdvancing(false)
    }
  }

  return (
    <div className="border border-border rounded-lg p-3 bg-card text-sm">
      {/* Card header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-foreground truncate">
            Propiedad #{deal.property_id}
          </p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            {DELIVERY_TYPE_LABELS[deal.delivery_type]} · {formatDate(deal.created_at)}
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <StageBadge stage={deal.stage} />
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-muted-foreground hover:text-foreground transition-colors p-0.5"
            aria-label={expanded ? 'Colapsar' : 'Ver detalle'}
          >
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* Expanded section */}
      {expanded && (
        <div className="mt-3 border-t border-border pt-3 space-y-3">
          <StageTimeline stage={deal.stage} />

          {canAdvance && !isTerminal && nextStage && (
            <Button
              size="sm"
              variant="outline"
              className="w-full h-7 text-xs"
              onClick={handleAdvance}
              disabled={advancing}
            >
              {advancing ? (
                <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
              ) : (
                <ArrowRight className="mr-1.5 h-3 w-3" />
              )}
              Avanzar a {STAGE_LABELS[nextStage]}
            </Button>
          )}

          {isTerminal && deal.stage === 'escritura_firmada' && (
            <div className="flex items-center gap-1.5 text-xs text-green-600">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>Deal completado</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Create deal modal ─────────────────────────────────────────────────────────

interface CreateDealModalProps {
  leadId: number
  open: boolean
  onClose: () => void
}

function CreateDealModal({ leadId, open, onClose }: CreateDealModalProps) {
  const { createDeal } = useDealsStore()
  const [query, setQuery] = useState('')
  const [properties, setProperties] = useState<Property[]>([])
  const [loadingProps, setLoadingProps] = useState(false)
  const [selectedProperty, setSelectedProperty] = useState<Property | null>(null)
  const [deliveryType, setDeliveryType] = useState<DeliveryType>('desconocida')
  const [submitting, setSubmitting] = useState(false)

  // Fetch available properties when modal opens or query changes
  useEffect(() => {
    if (!open) return
    const timer = setTimeout(async () => {
      setLoadingProps(true)
      try {
        const res = await propertiesService.getProperties({ status: 'available', limit: 50 })
        const items = res.data ?? []
        if (query.trim()) {
          const q = query.toLowerCase()
          setProperties(
            items.filter(
              (p) =>
                (p.name ?? '').toLowerCase().includes(q) ||
                (p.codigo ?? '').toLowerCase().includes(q) ||
                (p.project?.name ?? '').toLowerCase().includes(q),
            ),
          )
        } else {
          setProperties(items)
        }
      } catch {
        setProperties([])
      } finally {
        setLoadingProps(false)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [open, query])

  const handleClose = () => {
    setQuery('')
    setSelectedProperty(null)
    setDeliveryType('desconocida')
    onClose()
  }

  const handleSubmit = async () => {
    if (!selectedProperty) return
    setSubmitting(true)
    try {
      await createDeal({ lead_id: leadId, property_id: selectedProperty.id, delivery_type: deliveryType })
      toast.success('Deal creado correctamente')
      handleClose()
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Nuevo Deal</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 pt-1">
          {/* Property search */}
          <div className="space-y-1.5">
            <Label className="text-xs">Propiedad</Label>
            {selectedProperty ? (
              <div className="flex items-center justify-between p-2 border border-border rounded-md bg-muted/40 text-sm">
                <span className="truncate text-xs font-medium">
                  {selectedProperty.name ?? `#${selectedProperty.id}`}
                  {selectedProperty.codigo && (
                    <span className="text-muted-foreground ml-1">({selectedProperty.codigo})</span>
                  )}
                </span>
                <button
                  className="text-xs text-muted-foreground hover:text-foreground ml-2 shrink-0"
                  onClick={() => setSelectedProperty(null)}
                >
                  Cambiar
                </button>
              </div>
            ) : (
              <div className="space-y-1.5">
                <Input
                  placeholder="Buscar propiedad..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="h-8 text-xs"
                />
                <div className="border border-border rounded-md max-h-40 overflow-y-auto bg-white">
                  {loadingProps ? (
                    <div className="flex items-center justify-center py-4 text-xs text-muted-foreground">
                      <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> Cargando…
                    </div>
                  ) : properties.length === 0 ? (
                    <p className="text-xs text-muted-foreground text-center py-4">
                      Sin propiedades disponibles
                    </p>
                  ) : (
                    properties.map((p) => (
                      <button
                        key={p.id}
                        className="w-full text-left px-3 py-2 text-xs hover:bg-muted/50 transition-colors border-b border-border/50 last:border-0"
                        onClick={() => setSelectedProperty(p)}
                      >
                        <span className="font-medium block truncate">
                          {p.name ?? `Propiedad #${p.id}`}
                        </span>
                        {(p.codigo || p.project?.name) && (
                          <span className="text-muted-foreground">
                            {p.codigo ?? ''}{p.codigo && p.project?.name ? ' · ' : ''}{p.project?.name ?? ''}
                          </span>
                        )}
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Delivery type */}
          <div className="space-y-1.5">
            <Label className="text-xs">Tipo de entrega</Label>
            <Select value={deliveryType} onValueChange={(v) => setDeliveryType(v as DeliveryType)}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="inmediata">Inmediata</SelectItem>
                <SelectItem value="futura">Futura</SelectItem>
                <SelectItem value="desconocida">Desconocida</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Actions */}
          <div className="flex gap-2 justify-end pt-1">
            <Button variant="outline" size="sm" onClick={handleClose} disabled={submitting}>
              Cancelar
            </Button>
            <Button
              size="sm"
              onClick={handleSubmit}
              disabled={!selectedProperty || submitting}
            >
              {submitting && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
              Crear Deal
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── Main DealPanel ────────────────────────────────────────────────────────────

export function DealPanel({ leadId }: DealPanelProps) {
  const { dealsByLeadId, loading, error, loadDealsForLead } = useDealsStore()
  const { isAdmin, isAgent, role } = usePermissions()
  const [showCreate, setShowCreate] = useState(false)

  const deals = dealsByLeadId[leadId] ?? []
  const canWrite = isAdmin || isAgent
  const canAdvance = role !== 'viewer'

  useEffect(() => {
    loadDealsForLead(leadId).catch(() => {})
  }, [leadId, loadDealsForLead])

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Deals / Compraventas
        </h4>
        {canWrite && (
          <Button
            size="sm"
            variant="outline"
            className="h-6 text-xs px-2"
            onClick={() => setShowCreate(true)}
          >
            <Plus className="h-3 w-3 mr-1" />
            Nuevo Deal
          </Button>
        )}
      </div>

      {/* Content */}
      {loading && deals.length === 0 ? (
        <div className="flex items-center justify-center py-8 text-xs text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin mr-2" /> Cargando deals…
        </div>
      ) : error ? (
        <p className="text-xs text-destructive text-center py-6">{error}</p>
      ) : deals.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-center gap-2">
          <p className="text-xs text-muted-foreground">Sin deals para este lead.</p>
          {canWrite && (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-xs"
              onClick={() => setShowCreate(true)}
            >
              <Plus className="h-3 w-3 mr-1" />
              Crear primer deal
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-2 overflow-y-auto flex-1">
          {deals.map((deal: Deal) => (
            <DealCard key={deal.id} deal={deal} canAdvance={canAdvance} />
          ))}
        </div>
      )}

      <CreateDealModal
        leadId={leadId}
        open={showCreate}
        onClose={() => setShowCreate(false)}
      />
    </div>
  )
}
