import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  Loader2,
  XCircle,
  CheckCircle2,
  AlertCircle,
  Building2,
  User,
  Calendar,
  Truck,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/shared/components/ui/badge'
import { Button } from '@/shared/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/shared/components/ui/dialog'
import { Label } from '@/shared/components/ui/label'
import { Textarea } from '@/shared/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { useDealsStore } from '../store/dealsStore'
import { DealDocumentsBoard } from '../components/DealDocumentsBoard'
import { getErrorMessage } from '@/shared/types/api'
import { usePermissions } from '@/shared/hooks/usePermissions'
import type { DealStage } from '../types'

// ── Stage config ──────────────────────────────────────────────────────────────

const STAGE_ORDER: DealStage[] = [
  'draft',
  'reserva',
  'docs_pendientes',
  'en_aprobacion_bancaria',
  'promesa_redaccion',
  'promesa_firmada',
  'escritura_firmada',
]

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

const STAGE_BADGE: Record<DealStage, string> = {
  draft: 'bg-gray-100 text-gray-600 border-gray-200',
  reserva: 'bg-blue-100 text-blue-700 border-blue-200',
  docs_pendientes: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  en_aprobacion_bancaria: 'bg-orange-100 text-orange-700 border-orange-200',
  promesa_redaccion: 'bg-purple-100 text-purple-700 border-purple-200',
  promesa_firmada: 'bg-purple-200 text-purple-800 border-purple-300',
  escritura_firmada: 'bg-green-100 text-green-700 border-green-200',
  cancelado: 'bg-red-100 text-red-600 border-red-200',
}

const DELIVERY_LABELS: Record<string, string> = {
  inmediata: 'Entrega inmediata',
  futura: 'Entrega futura',
  desconocida: 'Por definir',
}

const CANCELLATION_REASONS = [
  { value: 'cliente_desistio', label: 'Cliente desistió' },
  { value: 'no_califico_banco', label: 'No calificó en banco' },
  { value: 'precio', label: 'Precio' },
  { value: 'otro', label: 'Otro' },
]

function getNextStage(current: DealStage): DealStage | null {
  const idx = STAGE_ORDER.indexOf(current)
  if (idx === -1 || idx === STAGE_ORDER.length - 1) return null
  return STAGE_ORDER[idx + 1]
}

// ── Stage timeline ────────────────────────────────────────────────────────────

function StageTimeline({ stage }: { stage: DealStage }) {
  const isCancelled = stage === 'cancelado'
  const currentIdx = STAGE_ORDER.indexOf(isCancelled ? 'draft' : stage)

  return (
    <div className="flex items-center gap-0 flex-wrap">
      {STAGE_ORDER.map((s, i) => {
        const isPast = i < currentIdx
        const isCurrent = s === stage && !isCancelled
        const isFuture = i > currentIdx

        return (
          <div key={s} className="flex items-center">
            <div className="flex flex-col items-center gap-1">
              <div
                className={`h-3 w-3 rounded-full border-2 shrink-0 ${
                  isCurrent
                    ? 'bg-blue-500 border-blue-500'
                    : isPast
                    ? 'bg-green-400 border-green-400'
                    : 'bg-gray-100 border-gray-300'
                } ${isFuture ? 'opacity-40' : ''}`}
                title={STAGE_LABELS[s]}
              />
              <span
                className={`text-[10px] whitespace-nowrap ${
                  isCurrent
                    ? 'text-blue-600 font-semibold'
                    : isPast
                    ? 'text-green-600'
                    : 'text-gray-400'
                }`}
              >
                {STAGE_LABELS[s]}
              </span>
            </div>
            {i < STAGE_ORDER.length - 1 && (
              <div
                className={`h-0.5 w-8 mb-4 mx-1 ${isPast ? 'bg-green-400' : 'bg-gray-200'}`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Cancel modal ──────────────────────────────────────────────────────────────

interface CancelModalProps {
  open: boolean
  onClose: () => void
  onConfirm: (reason: string, notes: string) => Promise<void>
}

function CancelModal({ open, onClose, onConfirm }: CancelModalProps) {
  const [reason, setReason] = useState('')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)

  const handleConfirm = async () => {
    if (!reason) return
    setLoading(true)
    try {
      await onConfirm(reason, notes)
      onClose()
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Cancelar negocio</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-1">
          <div className="space-y-1.5">
            <Label>Motivo</Label>
            <Select value={reason} onValueChange={setReason}>
              <SelectTrigger>
                <SelectValue placeholder="Selecciona motivo…" />
              </SelectTrigger>
              <SelectContent>
                {CANCELLATION_REASONS.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Notas (opcional)</Label>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Detalles adicionales…"
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Volver
          </Button>
          <Button variant="destructive" onClick={handleConfirm} disabled={!reason || loading}>
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Cancelar negocio
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function NegocioDealPage() {
  const { dealId } = useParams<{ dealId: string }>()
  const navigate = useNavigate()
  const { dealDetails, loadDealDetail, transitionDeal, cancelDeal } = useDealsStore()
  const { isAdmin, isAgent } = usePermissions()
  const canWrite = isAdmin || isAgent

  const [advancing, setAdvancing] = useState(false)
  const [showCancel, setShowCancel] = useState(false)

  const id = Number(dealId)
  const deal = dealDetails[id]

  useEffect(() => {
    if (id) loadDealDetail(id).catch(() => toast.error('No se pudo cargar el negocio'))
  }, [id, loadDealDetail])

  const handleAdvance = async () => {
    if (!deal) return
    const next = getNextStage(deal.stage)
    if (!next) return
    setAdvancing(true)
    try {
      await transitionDeal(id, { to_stage: next })
      toast.success(`Avanzado a "${STAGE_LABELS[next]}"`)
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setAdvancing(false)
    }
  }

  const handleCancel = async (reason: string, notes: string) => {
    try {
      await cancelDeal(id, { reason, notes })
      toast.success('Negocio cancelado')
    } catch (err) {
      toast.error(getErrorMessage(err))
      throw err
    }
  }

  if (!deal) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" /> Cargando negocio…
      </div>
    )
  }

  const nextStage = getNextStage(deal.stage)
  const isTerminal = deal.stage === 'escritura_firmada' || deal.stage === 'cancelado'

  return (
    <div className="p-4 sm:p-8 overflow-y-auto h-full space-y-6">
      {/* Back + header */}
      <div className="flex items-start gap-4">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 mt-0.5 shrink-0"
          onClick={() => navigate('/negocios')}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1 className="text-xl font-semibold text-slate-800">
              {deal.lead_name && deal.property_label
                ? `${deal.lead_name} — ${deal.property_label}`
                : deal.lead_name
                ? `${deal.lead_name} — Propiedad #${deal.property_id}`
                : `Negocio #${deal.id}`}
            </h1>
            <Badge
              variant="outline"
              className={`text-xs font-semibold ${STAGE_BADGE[deal.stage]}`}
            >
              {STAGE_LABELS[deal.stage]}
            </Badge>
          </div>
          {deal.stage === 'cancelado' && deal.cancellation_reason && (
            <p className="text-sm text-red-600 mt-1 flex items-center gap-1">
              <XCircle className="h-4 w-4" />
              Cancelado: {CANCELLATION_REASONS.find((r) => r.value === deal.cancellation_reason)?.label ?? deal.cancellation_reason}
              {deal.cancellation_notes && ` · ${deal.cancellation_notes}`}
            </p>
          )}
        </div>
      </div>

      {/* Info grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="flex items-center gap-2 bg-white border rounded-lg p-3">
          <User className="h-4 w-4 text-slate-400 shrink-0" />
          <div className="min-w-0">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Lead</p>
            <p className="text-sm font-medium truncate">{deal.lead_name ?? `#${deal.lead_id}`}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 bg-white border rounded-lg p-3">
          <Building2 className="h-4 w-4 text-slate-400 shrink-0" />
          <div className="min-w-0">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Propiedad</p>
            <p className="text-sm font-medium truncate">{deal.property_label ?? `#${deal.property_id}`}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 bg-white border rounded-lg p-3">
          <Truck className="h-4 w-4 text-slate-400 shrink-0" />
          <div className="min-w-0">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Entrega</p>
            <p className="text-sm font-medium">{DELIVERY_LABELS[deal.delivery_type] ?? deal.delivery_type}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 bg-white border rounded-lg p-3">
          <Calendar className="h-4 w-4 text-slate-400 shrink-0" />
          <div className="min-w-0">
            <p className="text-[10px] text-muted-foreground uppercase tracking-wide">Creado</p>
            <p className="text-sm font-medium">
              {new Date(deal.created_at).toLocaleDateString('es-CL')}
            </p>
          </div>
        </div>
      </div>

      {/* Stage timeline */}
      <div className="bg-white border rounded-lg p-4">
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-4">
          Progreso del negocio
        </h2>
        <div className="overflow-x-auto pb-1">
          <StageTimeline stage={deal.stage} />
        </div>

        {/* Actions */}
        {canWrite && !isTerminal && (
          <div className="flex items-center gap-2 mt-5 pt-4 border-t">
            {nextStage && (
              <Button onClick={handleAdvance} disabled={advancing} size="sm">
                {advancing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className="mr-2 h-4 w-4" />
                )}
                Avanzar a {STAGE_LABELS[nextStage]}
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              className="text-red-600 border-red-200 hover:bg-red-50"
              onClick={() => setShowCancel(true)}
            >
              <XCircle className="mr-2 h-4 w-4" />
              Cancelar negocio
            </Button>
          </div>
        )}

        {deal.stage === 'escritura_firmada' && (
          <div className="flex items-center gap-2 mt-4 pt-4 border-t text-green-600">
            <CheckCircle2 className="h-5 w-5" />
            <span className="text-sm font-medium">Negocio completado exitosamente</span>
          </div>
        )}

        {/* Jefatura/bank review indicators */}
        {deal.jefatura_review_required && (
          <div className={`flex items-center gap-2 mt-3 text-sm ${
            deal.jefatura_review_status === 'aprobado' ? 'text-green-600' :
            deal.jefatura_review_status === 'rechazado' ? 'text-red-600' : 'text-orange-600'
          }`}>
            <AlertCircle className="h-4 w-4 shrink-0" />
            Revisión de jefatura: {deal.jefatura_review_status ?? 'pendiente'}
            {deal.jefatura_review_notes && ` · ${deal.jefatura_review_notes}`}
          </div>
        )}
        {deal.bank_review_status && (
          <div className={`flex items-center gap-2 mt-2 text-sm ${
            deal.bank_review_status === 'aprobado' ? 'text-green-600' :
            deal.bank_review_status === 'rechazado' ? 'text-red-600' : 'text-orange-600'
          }`}>
            <AlertCircle className="h-4 w-4 shrink-0" />
            Revisión bancaria: {deal.bank_review_status}
          </div>
        )}
      </div>

      {/* Documents board */}
      <div className="bg-white border rounded-lg p-4">
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-4">
          Documentos requeridos
        </h2>
        <DealDocumentsBoard deal={deal} canEdit={canWrite && !isTerminal} />
      </div>

      <CancelModal
        open={showCancel}
        onClose={() => setShowCancel(false)}
        onConfirm={handleCancel}
      />
    </div>
  )
}
