import { useEffect, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
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
  CreditCard,
  Copy,
  FileText,
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
import { Input } from '@/shared/components/ui/input'
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
import type { DealStage, Payment, PaymentStatus } from '../types'

const CLP = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 })

const PAYMENT_STATUS_LABELS: Record<PaymentStatus, string> = {
  created: 'Link generado',
  pending: 'Esperando pago',
  approved: 'Pagado',
  failed: 'Rechazado',
  aborted: 'Anulado',
  cancelled: 'Link cancelado',
  error: 'Error',
}

const PAYMENT_STATUS_BADGE: Record<PaymentStatus, string> = {
  created: 'bg-gray-100 text-gray-600 border-gray-200',
  pending: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  approved: 'bg-green-100 text-green-700 border-green-200',
  failed: 'bg-red-100 text-red-600 border-red-200',
  aborted: 'bg-orange-100 text-orange-700 border-orange-200',
  cancelled: 'bg-gray-100 text-gray-500 border-gray-200',
  error: 'bg-red-100 text-red-600 border-red-200',
}

const PAYMENT_TYPE_LABELS: Record<string, string> = {
  VD: 'Débito',
  VN: 'Crédito',
  VC: 'Crédito',
  SI: 'Crédito sin interés',
  S2: 'Crédito en cuotas',
  NC: 'Crédito',
}

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

// ── Payment link modal ─────────────────────────────────────────────────────────

interface PaymentModalProps {
  open: boolean
  dealId: number
  onClose: () => void
}

function PaymentModal({ open, dealId, onClose }: PaymentModalProps) {
  const createPaymentLink = useDealsStore((s) => s.createPaymentLink)
  const [amount, setAmount] = useState('')
  const [loading, setLoading] = useState(false)
  const [payUrl, setPayUrl] = useState<string | null>(null)

  const reset = () => {
    setAmount('')
    setPayUrl(null)
    setLoading(false)
  }

  const handleClose = () => {
    reset()
    onClose()
  }

  const handleGenerate = async () => {
    const value = Number(amount)
    if (!value || value <= 0) {
      toast.error('Ingresa un monto válido')
      return
    }
    setLoading(true)
    try {
      const res = await createPaymentLink(dealId, Math.round(value))
      setPayUrl(res.pay_url)
      toast.success('Link de pago generado')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = async () => {
    if (!payUrl) return
    try {
      await navigator.clipboard.writeText(payUrl)
      toast.success('Link copiado')
    } catch {
      toast.error('No se pudo copiar')
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Generar link de pago · Transbank</DialogTitle>
        </DialogHeader>
        {!payUrl ? (
          <div className="space-y-4 py-1">
            <div className="space-y-1.5">
              <Label>Monto de la reserva (CLP)</Label>
              <Input
                type="number"
                inputMode="numeric"
                min={1}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="Ej: 100000"
              />
              {Number(amount) > 0 && (
                <p className="text-xs text-muted-foreground">{CLP.format(Number(amount))}</p>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-3 py-1">
            <p className="text-sm text-muted-foreground">
              Comparte este link con el comprador para que pague la reserva:
            </p>
            <div className="flex items-center gap-2">
              <Input readOnly value={payUrl} className="text-xs" />
              <Button variant="outline" size="icon" onClick={handleCopy} title="Copiar link">
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
        <DialogFooter>
          {!payUrl ? (
            <>
              <Button variant="outline" onClick={handleClose} disabled={loading}>
                Cancelar
              </Button>
              <Button onClick={handleGenerate} disabled={loading || !amount}>
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Generar link
              </Button>
            </>
          ) : (
            <Button onClick={handleClose}>Listo</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Comprobante (receipt) modal ─────────────────────────────────────────────────

function ReceiptModal({ payment, onClose }: { payment: Payment | null; onClose: () => void }) {
  const rows: [string, string][] = payment
    ? [
        ['Monto', CLP.format(payment.amount)],
        ['Estado', PAYMENT_STATUS_LABELS[payment.status]],
        ['Código de autorización', payment.authorization_code ?? '—'],
        ['Tarjeta', payment.card_last4 ? `•••• ${payment.card_last4}` : '—'],
        ['Tipo de pago', payment.payment_type_code ? (PAYMENT_TYPE_LABELS[payment.payment_type_code] ?? payment.payment_type_code) : '—'],
        ['Cuotas', payment.installments_number != null ? String(payment.installments_number) : '—'],
        ['Fecha de transacción', payment.transaction_date ? new Date(payment.transaction_date).toLocaleString('es-CL') : '—'],
        ['Orden de compra', payment.buy_order],
        ['Ambiente', payment.environment === 'integration' ? 'Integración (test)' : 'Producción'],
      ]
    : []

  return (
    <Dialog open={!!payment} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Comprobante de pago · Transbank</DialogTitle>
        </DialogHeader>
        <div className="divide-y border rounded-md">
          {rows.map(([k, v]) => (
            <div key={k} className="flex items-center justify-between gap-3 px-3 py-2">
              <span className="text-xs text-muted-foreground">{k}</span>
              <span className="text-sm font-medium text-right break-all">{v}</span>
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => window.print()}>Imprimir</Button>
          <Button onClick={onClose}>Cerrar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Payments section ────────────────────────────────────────────────────────────

function PaymentsSection({
  payments,
  dealId,
  canWrite,
}: {
  payments: Payment[]
  dealId: number
  canWrite: boolean
}) {
  const cancelPayment = useDealsStore((s) => s.cancelPayment)
  const [receipt, setReceipt] = useState<Payment | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  if (!payments.length) return null

  const copyLink = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url)
      toast.success('Link copiado')
    } catch {
      toast.error('No se pudo copiar')
    }
  }

  const handleCancel = async (paymentId: number) => {
    setBusyId(paymentId)
    try {
      await cancelPayment(dealId, paymentId)
      toast.success('Link de pago cancelado')
    } catch (err) {
      toast.error(getErrorMessage(err))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="bg-white border rounded-lg p-4">
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-4">
        Pagos de reserva
      </h2>
      <div className="space-y-2">
        {payments.map((p) => {
          const isPayable = p.status === 'created' || p.status === 'pending'
          return (
            <div
              key={p.id}
              className="flex items-center justify-between gap-3 border rounded-md px-3 py-2"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium">{CLP.format(p.amount)}</p>
                <p className="text-[11px] text-muted-foreground truncate">
                  {new Date(p.created_at).toLocaleString('es-CL')}
                  {p.authorization_code && ` · Aut: ${p.authorization_code}`}
                  {p.card_last4 && ` · ••••${p.card_last4}`}
                  {p.environment === 'integration' && ' · (test)'}
                </p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                {p.status === 'approved' && (
                  <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={() => setReceipt(p)}>
                    <FileText className="h-3.5 w-3.5 mr-1" /> Comprobante
                  </Button>
                )}
                {isPayable && p.pay_url && (
                  <Button variant="ghost" size="icon" className="h-7 w-7" title="Copiar link" onClick={() => copyLink(p.pay_url!)}>
                    <Copy className="h-3.5 w-3.5" />
                  </Button>
                )}
                {isPayable && canWrite && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs text-red-600 hover:bg-red-50"
                    disabled={busyId === p.id}
                    onClick={() => handleCancel(p.id)}
                  >
                    {busyId === p.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'Cancelar'}
                  </Button>
                )}
                <Badge variant="outline" className={`text-xs font-semibold ${PAYMENT_STATUS_BADGE[p.status]}`}>
                  {PAYMENT_STATUS_LABELS[p.status]}
                </Badge>
              </div>
            </div>
          )
        })}
      </div>
      <ReceiptModal payment={receipt} onClose={() => setReceipt(null)} />
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function NegocioDealPage() {
  const { dealId } = useParams<{ dealId: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { dealDetails, loadDealDetail, transitionDeal, cancelDeal, loadPayments, paymentsByDealId } =
    useDealsStore()
  const { isAdmin, isAgent } = usePermissions()
  const canWrite = isAdmin || isAgent

  const [advancing, setAdvancing] = useState(false)
  const [showCancel, setShowCancel] = useState(false)
  const [showPayment, setShowPayment] = useState(false)

  const id = Number(dealId)
  const deal = dealDetails[id]
  const payments = paymentsByDealId[id] ?? []

  useEffect(() => {
    if (id) loadDealDetail(id).catch(() => toast.error('No se pudo cargar el negocio'))
    if (id) loadPayments(id)
  }, [id, loadDealDetail, loadPayments])

  // Handle Transbank return redirect (?payment=success|failed|aborted)
  useEffect(() => {
    const status = searchParams.get('payment')
    if (!status || !id) return
    if (status === 'success') toast.success('Pago aprobado — negocio avanzado a Reserva')
    else if (status === 'aborted') toast.warning('El comprador anuló el pago')
    else toast.error('El pago no se pudo completar')
    loadPayments(id)
    loadDealDetail(id).catch(() => {})
    searchParams.delete('payment')
    setSearchParams(searchParams, { replace: true })
  }, [searchParams, id, loadPayments, loadDealDetail, setSearchParams])

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
            {deal.stage === 'draft' && (
              <Button
                variant="outline"
                size="sm"
                className="text-blue-700 border-blue-200 hover:bg-blue-50"
                onClick={() => setShowPayment(true)}
              >
                <CreditCard className="mr-2 h-4 w-4" />
                Generar link de pago
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

      {/* Payments */}
      <PaymentsSection payments={payments} dealId={id} canWrite={canWrite} />

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

      <PaymentModal
        open={showPayment}
        dealId={id}
        onClose={() => setShowPayment(false)}
      />
    </div>
  )
}
