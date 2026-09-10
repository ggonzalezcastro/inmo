import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CalendarDays,
  Check,
  CircleDollarSign,
  Eye,
  FileInput,
  FormInput,
  Gauge,
  GitCompare,
  Loader2,
  Megaphone,
  MousePointerClick,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Users,
  WalletCards,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import { Link, useSearchParams } from 'react-router-dom'
import { Button } from '@/shared/components/ui/button'
import { EmptyState } from '@/shared/components/common/EmptyState'
import { LoadingSpinner } from '@/shared/components/common/LoadingSpinner'
import { PageHeader } from '@/shared/components/common/PageHeader'
import { useAuthStore } from '@/features/auth'
import { useWebSocketEvent } from '@/shared/context/WebSocketContext'
import { getErrorMessage } from '@/shared/types/api'
import { cn } from '@/shared/lib/utils'
import { metaService } from '../services/meta.service'
import type {
  MetaAdCampaign,
  MetaAdCampaignPayload,
  MetaAdsAnalytics,
  MetaAdsPolicy,
  MetaAsset,
  MetaLeadForm,
  MetaLeadFormPreview,
  BrokerUser,
} from '../types'

type Tab = 'overview' | 'campaigns' | 'forms' | 'conversions' | 'policy'
type WizardStep = 1 | 2 | 3 | 4

const inputClass = 'h-10 w-full rounded-xl border border-[#DCE5F2] bg-white px-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-[#1A56DB] focus:ring-2 focus:ring-blue-100'
const labelClass = 'mb-1.5 block text-[11px] font-bold uppercase tracking-[0.08em] text-slate-500'

const STATUS: Record<MetaAdCampaign['status'], { label: string; className: string }> = {
  draft: { label: 'Borrador', className: 'bg-slate-100 text-slate-700' },
  pending_review: { label: 'En revisión', className: 'bg-amber-50 text-amber-700' },
  rejected: { label: 'Rechazada', className: 'bg-rose-50 text-rose-700' },
  approved: { label: 'Aprobada', className: 'bg-indigo-50 text-indigo-700' },
  publishing: { label: 'Publicando', className: 'bg-blue-50 text-blue-700' },
  published_paused: { label: 'Publicada · pausada', className: 'bg-violet-50 text-violet-700' },
  active: { label: 'Activa', className: 'bg-emerald-50 text-emerald-700' },
  paused: { label: 'Pausada', className: 'bg-slate-100 text-slate-600' },
  completed: { label: 'Finalizada', className: 'bg-slate-100 text-slate-500' },
  partial_error: { label: 'Error parcial', className: 'bg-rose-50 text-rose-700' },
}

function money(value: number | null | undefined, currency = 'CLP') {
  if (value == null) return '—'
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency, maximumFractionDigits: currency === 'CLP' ? 0 : 2 }).format(value)
}

function compact(value: number) {
  return new Intl.NumberFormat('es-CL', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

function currentCampaignSnapshot(campaign: MetaAdCampaign): Record<string, unknown> {
  const adSet = campaign.ad_sets[0]
  const creative = campaign.creatives[0]
  return {
    name: campaign.name,
    ad_account_asset_id: campaign.ad_account_asset_id,
    project_id: campaign.project_id,
    objective: campaign.objective,
    destination_type: campaign.destination_type,
    special_ad_category: campaign.special_ad_category,
    daily_budget: campaign.daily_budget,
    lifetime_budget: campaign.lifetime_budget,
    currency: campaign.currency,
    ad_set: adSet ? {
      name: adSet.name,
      optimization_goal: adSet.optimization_goal,
      billing_event: adSet.billing_event,
      targeting: adSet.targeting,
      promoted_object: adSet.promoted_object,
      start_at: adSet.start_at,
      end_at: adSet.end_at,
    } : null,
    creative: creative ? {
      page_asset_id: creative.page_asset_id,
      instagram_asset_id: creative.instagram_asset_id,
      name: creative.name,
      primary_text: creative.primary_text,
      headline: creative.headline,
      description: creative.description,
      call_to_action: creative.call_to_action,
      destination_url: creative.destination_url,
      media_url: creative.media_url,
      media_hash: creative.media_hash,
    } : null,
  }
}

function flattenSnapshot(value: unknown, prefix = '', result: Record<string, unknown> = {}) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    Object.entries(value as Record<string, unknown>).forEach(([key, nested]) => {
      flattenSnapshot(nested, prefix ? `${prefix}.${key}` : key, result)
    })
  } else {
    result[prefix] = value
  }
  return result
}

function comparable(value: unknown) {
  if (typeof value === 'string' && /^-?\d+(\.\d+)?$/.test(value)) return Number(value)
  return value == null ? null : value
}

function campaignDiff(campaign: MetaAdCampaign) {
  if (!campaign.submission_snapshot) return []
  const submitted = flattenSnapshot(campaign.submission_snapshot)
  const current = flattenSnapshot(currentCampaignSnapshot(campaign))
  return Array.from(new Set([...Object.keys(submitted), ...Object.keys(current)]))
    .filter((key) => key !== 'version')
    .filter((key) => JSON.stringify(comparable(submitted[key])) !== JSON.stringify(comparable(current[key])))
    .map((key) => ({ key, submitted: submitted[key], current: current[key] }))
}

function displaySnapshotValue(value: unknown) {
  if (value == null || value === '') return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function CampaignReviewModal({ campaign, busy, onClose, onDecision }: {
  campaign: MetaAdCampaign
  busy: boolean
  onClose: () => void
  onDecision: (decision: 'approve' | 'reject', comment?: string) => void
}) {
  const [comment, setComment] = useState('')
  const changes = campaignDiff(campaign)
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="campaign-review-title" className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/50 p-0 backdrop-blur-[2px] sm:items-center sm:p-6" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onClose() }}>
      <div className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl sm:rounded-3xl">
        <header className="flex items-start justify-between border-b border-slate-100 px-5 py-4 sm:px-6">
          <div><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#1A56DB]">Control de publicación</p><h2 id="campaign-review-title" className="mt-1 text-lg font-bold text-slate-900">Revisión de campaña</h2><p className="mt-1 text-xs text-slate-500">Compara el contenido actual con la copia inmutable enviada por el ejecutivo.</p></div>
          <button aria-label="Cerrar revisión" disabled={busy} className="rounded-xl p-2 text-slate-400 hover:bg-slate-100" onClick={onClose}><X className="h-5 w-5" /></button>
        </header>
        <div className="flex-1 overflow-y-auto p-5 sm:p-6">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Campaña</p><p className="mt-1 text-sm font-bold text-slate-900">{campaign.name}</p></div>
            <div className="rounded-xl border border-slate-200 p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Presupuesto</p><p className="mt-1 text-sm font-bold text-slate-900">{money(campaign.daily_budget || campaign.lifetime_budget, campaign.currency)} {campaign.daily_budget ? '/ día' : 'total'}</p></div>
            <div className="rounded-xl border border-slate-200 p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">Destino</p><p className="mt-1 text-sm font-bold capitalize text-slate-900">{campaign.destination_type}</p></div>
          </div>
          <section className="mt-5 overflow-hidden rounded-2xl border border-slate-200">
            <header className="flex items-center gap-2 border-b border-slate-100 bg-slate-50 px-4 py-3"><GitCompare className="h-4 w-4 text-[#1A56DB]" /><div><h3 className="text-xs font-bold text-slate-900">Diferencias desde el envío</h3><p className="mt-0.5 text-[11px] text-slate-500">Snapshot capturado al solicitar aprobación.</p></div></header>
            {!campaign.submission_snapshot ? <p className="px-4 py-5 text-xs font-semibold text-amber-700">No existe snapshot de envío. Recarga la campaña antes de decidir.</p> : changes.length === 0 ? <p className="flex items-center gap-2 px-4 py-5 text-xs font-semibold text-emerald-700"><Check className="h-4 w-4" /> Sin cambios desde el envío.</p> : <div className="divide-y divide-slate-100">{changes.map((change) => <div key={change.key} className="grid gap-2 px-4 py-3 text-xs sm:grid-cols-[160px_1fr_1fr]"><span className="font-semibold text-slate-600">{change.key.replace(/_/g, ' ')}</span><span className="break-words rounded-lg bg-slate-50 px-2 py-1.5 text-slate-500">Antes: {displaySnapshotValue(change.submitted)}</span><span className="break-words rounded-lg bg-amber-50 px-2 py-1.5 text-amber-900">Ahora: {displaySnapshotValue(change.current)}</span></div>)}</div>}
          </section>
          <label className="mt-5 block"><span className={labelClass}>Motivo si rechazas</span><textarea aria-label="Motivo del rechazo" rows={3} className={cn(inputClass, 'h-auto py-3')} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Explica qué debe corregir el ejecutivo…" /></label>
        </div>
        <footer className="flex flex-col-reverse gap-2 border-t border-slate-100 px-5 py-4 sm:flex-row sm:justify-end sm:px-6"><Button variant="outline" disabled={busy || !comment.trim()} onClick={() => onDecision('reject', comment.trim())}>Rechazar con comentario</Button><Button disabled={busy || !campaign.submission_snapshot} onClick={() => onDecision('approve')}>{busy && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />} Aprobar snapshot</Button></footer>
      </div>
    </div>
  )
}

function ActivationModal({ campaign, accountName, busy, onClose, onActivate }: {
  campaign: MetaAdCampaign
  accountName: string
  busy: boolean
  onClose: () => void
  onActivate: () => void
}) {
  const [confirmed, setConfirmed] = useState(false)
  const adSet = campaign.ad_sets[0]
  const start = adSet?.start_at ? new Date(adSet.start_at) : null
  const end = adSet?.end_at ? new Date(adSet.end_at) : null
  const activeDays = start && end ? Math.max(1, Math.ceil((end.getTime() - start.getTime()) / 86_400_000)) : null
  const maximum = campaign.lifetime_budget != null
    ? money(campaign.lifetime_budget, campaign.currency)
    : activeDays && campaign.daily_budget != null
      ? `${money(campaign.daily_budget * activeDays, campaign.currency)} · ${activeDays} días`
      : `${money(campaign.daily_budget, campaign.currency)} por día · sin tope total`
  return (
    <div role="dialog" aria-modal="true" aria-labelledby="activation-title" className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/50 p-0 backdrop-blur-[2px] sm:items-center sm:p-6" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onClose() }}>
      <div className="w-full max-w-xl overflow-hidden rounded-t-3xl bg-white shadow-2xl sm:rounded-3xl">
        <header className="flex items-start justify-between border-b border-slate-100 px-5 py-4 sm:px-6"><div><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-rose-600">Acción con gasto real</p><h2 id="activation-title" className="mt-1 text-lg font-bold text-slate-900">Confirmar activación de gasto</h2><p className="mt-1 text-xs text-slate-500">Meta comenzará a entregar anuncios cuando confirmes.</p></div><button aria-label="Cerrar activación" disabled={busy} className="rounded-xl p-2 text-slate-400 hover:bg-slate-100" onClick={onClose}><X className="h-5 w-5" /></button></header>
        <div className="p-5 sm:p-6">
          <div className="space-y-2.5">{([
            ['Cuenta publicitaria', accountName, WalletCards],
            ['Presupuesto', `${money(campaign.daily_budget || campaign.lifetime_budget, campaign.currency)} ${campaign.daily_budget ? '/ día' : 'total'}`, CircleDollarSign],
            ['Fechas', `${start ? start.toLocaleString('es-CL') : 'Inicio inmediato'} — ${end ? end.toLocaleString('es-CL') : 'sin fecha de término'}`, CalendarDays],
          ] as Array<[string, string, typeof WalletCards]>).map(([label, value, Icon]) => <div key={label} className="flex gap-3 rounded-xl border border-slate-200 p-3"><Icon className="mt-0.5 h-4 w-4 shrink-0 text-[#1A56DB]" /><div><p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">{label}</p><p className="mt-0.5 text-xs font-semibold text-slate-800">{value}</p></div></div>)}</div>
          <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-4"><p className="text-[10px] font-bold uppercase tracking-wide text-rose-600">Gasto máximo esperado</p><p className="mt-1 text-xl font-bold text-rose-950">{maximum}</p><p className="mt-1 text-[11px] leading-5 text-rose-700">La facturación efectiva depende de la entrega de Meta y puede detenerse antes pausando la campaña.</p></div>
          <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-3 text-xs font-semibold leading-5 text-slate-700"><input aria-label="Confirmo el gasto" type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} className="mt-0.5 h-4 w-4 accent-[#1A56DB]" /> Confirmo que revisé cuenta, presupuesto, fechas y gasto máximo esperado.</label>
        </div>
        <footer className="flex justify-end gap-2 border-t border-slate-100 px-5 py-4 sm:px-6"><Button variant="ghost" disabled={busy} onClick={onClose}>Cancelar</Button><Button disabled={busy || !confirmed} onClick={onActivate}>{busy && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />} Activar campaña y comenzar gasto</Button></footer>
      </div>
    </div>
  )
}

const STANDARD_FORM_TARGETS: Record<string, string> = {
  full_name: 'name', name: 'name', first_name: 'first_name', last_name: 'last_name',
  phone_number: 'phone', phone: 'phone', email: 'email',
}

function formQuestionKey(question: Record<string, unknown>, index: number) {
  return String(question.key || question.id || question.label || `question_${index}`).trim().toLowerCase()
}

function sampleForField(target: string, source: string) {
  if (target === 'name' || target === 'first_name' || target === 'last_name') return 'María Soto'
  if (target === 'phone') return '9 1234 5678'
  if (target === 'email') return 'maria@example.com'
  if (target === 'budget') return '3.500 UF'
  if (target === 'commune') return 'Ñuñoa'
  if (target === 'message') return 'Quiero conocer disponibilidad'
  return source.includes('phone') ? '9 1234 5678' : source.includes('email') ? 'maria@example.com' : 'Respuesta de ejemplo'
}

function LeadFormEditor({ form, projects, onSaved }: {
  form: MetaLeadForm
  projects: Array<{ id: number; name: string; status: string }>
  onSaved: (form: MetaLeadForm) => void
}) {
  const initialMapping = useMemo(() => Object.fromEntries(form.questions.map((question, index) => {
    const key = formQuestionKey(question, index)
    return [key, form.field_mapping[key] || STANDARD_FORM_TARGETS[key] || '']
  })), [form])
  const [projectId, setProjectId] = useState<number | null>(form.project_id)
  const [mapping, setMapping] = useState<Record<string, string>>(initialMapping)
  const [samples, setSamples] = useState<Record<string, string>>(() => Object.fromEntries(form.questions.map((question, index) => {
    const key = formQuestionKey(question, index)
    return [key, sampleForField(initialMapping[key], key)]
  })))
  const [preview, setPreview] = useState<MetaLeadFormPreview | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [saving, setSaving] = useState(false)
  const cleanMapping = useMemo(() => Object.fromEntries(Object.entries(mapping).filter(([, target]) => target)), [mapping])

  const runPreview = async () => {
    setPreviewing(true)
    try {
      setPreview(await metaService.previewLeadForm(form.id, { project_id: projectId, field_mapping: cleanMapping, sample_values: samples }))
    } catch (error) {
      setPreview(null)
      toast.error(getErrorMessage(error))
    } finally {
      setPreviewing(false)
    }
  }

  const save = async () => {
    if (!preview) return
    setSaving(true)
    try {
      onSaved(await metaService.updateLeadForm(form.id, { project_id: projectId, field_mapping: cleanMapping }))
      toast.success('Mapeo de formulario guardado')
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mt-4 grid gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-4 lg:grid-cols-[1.15fr_0.85fr]">
      <div>
        <label><span className={labelClass}>Proyecto asociado</span><select className={inputClass} value={projectId || ''} onChange={(event) => { setProjectId(event.target.value ? Number(event.target.value) : null); setPreview(null) }}><option value="">Sin proyecto</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
        <div className="mt-4 space-y-3">{form.questions.map((question, index) => { const key = formQuestionKey(question, index); const label = String(question.label || key); return <div key={key} className="rounded-xl border border-slate-200 bg-white p-3"><p className="mb-2 text-xs font-bold text-slate-800">{label}</p><div className="grid gap-2 sm:grid-cols-2"><label><span className={labelClass}>Campo CRM</span><select aria-label={`Campo CRM para ${label}`} className={inputClass} value={mapping[key] || ''} onChange={(event) => { const target = event.target.value; setMapping((current) => ({ ...current, [key]: target })); setSamples((current) => ({ ...current, [key]: sampleForField(target, key) })); setPreview(null) }}><option value="">Seleccionar campo</option><option value="name">Nombre</option><option value="first_name">Nombre de pila</option><option value="last_name">Apellido</option><option value="phone">Teléfono</option><option value="email">Email</option><option value="budget">Presupuesto</option><option value="commune">Comuna</option><option value="message">Mensaje</option><option value="ignore">Ignorar</option></select></label><label><span className={labelClass}>Valor de ejemplo</span><input aria-label={`Ejemplo para ${label}`} className={inputClass} value={samples[key] || ''} disabled={mapping[key] === 'ignore'} onChange={(event) => { setSamples((current) => ({ ...current, [key]: event.target.value })); setPreview(null) }} /></label></div></div> })}</div>
        <div className="mt-4 flex flex-wrap justify-end gap-2"><Button variant="outline" size="sm" disabled={previewing} onClick={runPreview}>{previewing ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Eye className="mr-1.5 h-4 w-4" />} Previsualizar lead</Button><Button size="sm" disabled={!preview || saving} onClick={save}>{saving && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />} Guardar mapeo</Button></div>
      </div>
      <aside className="min-h-64 overflow-hidden rounded-2xl border border-[#C8D9F2] bg-white">
        <header className="border-b border-blue-100 bg-blue-50 px-4 py-3"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#1A56DB]">Sin guardar</p><h3 className="mt-0.5 text-sm font-bold text-slate-900">Vista previa del lead</h3></header>
        {!preview ? <div className="flex min-h-52 flex-col items-center justify-center px-5 text-center"><FormInput className="h-7 w-7 text-slate-300" /><p className="mt-3 text-xs font-semibold text-slate-600">Completa el mapeo y previsualiza el resultado.</p><p className="mt-1 text-[11px] leading-5 text-slate-400">Nada se persistirá hasta que guardes.</p></div> : <div className="p-4"><div className="space-y-2">{[['Nombre', preview.lead_payload.name], ['Teléfono', preview.lead_payload.phone], ['Email', preview.lead_payload.email], ['Proyecto', preview.lead_payload.metadata.project_id]].map(([label, value]) => <div key={String(label)} className="flex items-start justify-between gap-3 border-b border-slate-100 pb-2 text-xs"><span className="text-slate-400">{label as string}</span><span className="break-all text-right font-semibold text-slate-800">{displaySnapshotValue(value)}</span></div>)}</div><div className="mt-3"><p className={labelClass}>Metadata resultante</p><pre className="max-h-36 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-slate-950 p-3 text-[10px] leading-5 text-slate-100">{JSON.stringify(preview.lead_payload.metadata, null, 2)}</pre></div>{preview.warnings.length > 0 && <div className="mt-3 space-y-1.5">{preview.warnings.map((warning) => <p key={warning} className="rounded-lg bg-amber-50 px-2.5 py-2 text-[10px] font-semibold leading-4 text-amber-800">{warning}</p>)}</div>}</div>}
      </aside>
    </div>
  )
}

interface CampaignDraft {
  name: string
  accountId: string
  projectId: string
  objective: MetaAdCampaignPayload['objective']
  destination: MetaAdCampaignPayload['destination_type']
  destinationAssetId: string
  pageId: string
  instagramId: string
  budgetType: 'daily' | 'lifetime'
  budget: string
  startAt: string
  endAt: string
  primaryText: string
  headline: string
  description: string
  destinationUrl: string
  mediaUrl: string
  cta: string
}

const EMPTY_DRAFT: CampaignDraft = {
  name: '', accountId: '', projectId: '', objective: 'OUTCOME_LEADS', destination: 'lead_form',
  destinationAssetId: '', pageId: '', instagramId: '', budgetType: 'daily', budget: '',
  startAt: '', endAt: '', primaryText: '', headline: '', description: '', destinationUrl: '', mediaUrl: '', cta: 'LEARN_MORE',
}

function Wizard({ assets, forms, projects, policy, storageKey, onClose, onSaved }: {
  assets: MetaAsset[]
  forms: MetaLeadForm[]
  projects: Array<{ id: number; name: string; status: string }>
  policy: MetaAdsPolicy
  storageKey: string
  onClose: () => void
  onSaved: (campaign: MetaAdCampaign) => void
}) {
  const restored = useMemo(() => {
    try { return JSON.parse(window.localStorage.getItem(storageKey) || 'null') as { step?: WizardStep; draft?: CampaignDraft } | null } catch { return null }
  }, [storageKey])
  const [step, setStep] = useState<WizardStep>(restored?.step || 1)
  const [draft, setDraft] = useState<CampaignDraft>(restored?.draft ? { ...EMPTY_DRAFT, ...restored.draft } : EMPTY_DRAFT)
  const [saving, setSaving] = useState(false)
  const accounts = assets.filter((asset) => asset.asset_type === 'ad_account' && asset.status === 'active')
  const pages = assets.filter((asset) => asset.asset_type === 'facebook_page' && asset.status === 'active')
  const instagrams = assets.filter((asset) => asset.asset_type === 'instagram_account' && asset.status === 'active')
  const numbers = assets.filter((asset) => asset.asset_type === 'whatsapp_phone' && asset.status === 'active')
  const pageForms = forms.filter((form) => !draft.pageId || form.page_asset_id === Number(draft.pageId))
  const limit = draft.budgetType === 'daily' ? policy.max_daily_budget : policy.max_lifetime_budget

  useEffect(() => {
    window.localStorage.setItem(storageKey, JSON.stringify({ step, draft }))
  }, [draft, step, storageKey])

  const update = <K extends keyof CampaignDraft>(key: K, value: CampaignDraft[K]) => setDraft((current) => ({ ...current, [key]: value }))

  const validateStep = () => {
    if (step === 1 && (!draft.name.trim() || !draft.accountId || !draft.projectId)) return 'Completa nombre, cuenta y proyecto.'
    if (step === 2 && (!draft.pageId || !draft.destinationAssetId || !draft.budget || Number(draft.budget) <= 0)) return 'Completa destino, activo y presupuesto.'
    if (step === 2 && Number(draft.budget) > Number(limit)) return 'El presupuesto supera el máximo aprobado por jefatura.'
    if (step === 3 && (!draft.primaryText.trim() || !draft.headline.trim())) return 'El texto principal y el titular son obligatorios.'
    if (step === 3 && draft.destination === 'website' && !draft.destinationUrl.startsWith('https://')) return 'La URL de destino debe comenzar con https://'
    return null
  }

  const next = () => {
    const error = validateStep()
    if (error) return toast.error(error)
    setStep((current) => Math.min(4, current + 1) as WizardStep)
  }

  const save = async () => {
    const account = accounts.find((item) => item.id === Number(draft.accountId))
    const page = pages.find((item) => item.id === Number(draft.pageId))
    const destinationAsset = assets.find((item) => item.id === Number(draft.destinationAssetId))
    const selectedForm = forms.find((item) => item.id === Number(draft.destinationAssetId))
    const validDestination = draft.destination === 'lead_form'
      ? !!selectedForm
      : draft.destination === 'website' || !!destinationAsset
    if (!account || !page || !validDestination) return toast.error('Revisa los activos seleccionados')
    const promotedObject: Record<string, unknown> = {}
    if (draft.destination === 'lead_form') promotedObject.page_id = page.external_id
    if (draft.destination === 'lead_form') promotedObject.lead_gen_form_id = selectedForm?.external_id
    if (draft.destination === 'whatsapp') promotedObject.whatsapp_phone_number = destinationAsset?.external_id
    if (draft.destination === 'instagram') promotedObject.instagram_actor_id = destinationAsset?.external_id
    const payload: MetaAdCampaignPayload = {
      name: draft.name.trim(),
      ad_account_asset_id: account.id,
      project_id: Number(draft.projectId),
      objective: draft.objective,
      destination_type: draft.destination,
      special_ad_category: 'HOUSING',
      currency: policy.currency,
      ...(draft.budgetType === 'daily' ? { daily_budget: Number(draft.budget) } : { lifetime_budget: Number(draft.budget) }),
      ad_set: {
        name: `${draft.name.trim()} · Audiencia`,
        optimization_goal: draft.destination === 'lead_form' ? 'LEAD_GENERATION' : draft.destination === 'website' ? 'LINK_CLICKS' : 'CONVERSATIONS',
        billing_event: 'IMPRESSIONS',
        targeting: { geo_locations: { countries: ['CL'] }, targeting_automation: { advantage_audience: 1 } },
        promoted_object: promotedObject,
        ...(draft.startAt ? { start_at: new Date(draft.startAt).toISOString() } : {}),
        ...(draft.endAt ? { end_at: new Date(draft.endAt).toISOString() } : {}),
      },
      creative: {
        page_asset_id: page.id,
        ...(draft.instagramId ? { instagram_asset_id: Number(draft.instagramId) } : {}),
        name: `${draft.name.trim()} · Creatividad`,
        primary_text: draft.primaryText.trim(),
        headline: draft.headline.trim(),
        description: draft.description.trim() || undefined,
        call_to_action: draft.cta,
        destination_url: draft.destinationUrl.trim() || undefined,
        media_url: draft.mediaUrl.trim() || undefined,
      },
    }
    setSaving(true)
    try {
      const campaign = await metaService.createAdCampaign(payload)
      window.localStorage.removeItem(storageKey)
      toast.success('Borrador publicitario guardado')
      onSaved(campaign)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  const destinationOptions = draft.destination === 'lead_form'
    ? pageForms.map((form) => ({ id: form.id, external: form.external_id, label: form.name }))
    : draft.destination === 'whatsapp'
      ? numbers.map((asset) => ({ id: asset.id, external: asset.external_id, label: asset.display_name || asset.external_id }))
      : draft.destination === 'instagram'
        ? instagrams.map((asset) => ({ id: asset.id, external: asset.external_id, label: asset.display_name || asset.external_id }))
        : [{ id: -1, external: 'website', label: 'Sitio web del proyecto' }]

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/45 p-0 backdrop-blur-[2px] sm:items-center sm:p-6">
      <div className="flex max-h-[94vh] w-full max-w-4xl flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl sm:rounded-3xl">
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-4 sm:px-7"><div><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#1A56DB]">Nueva campaña Meta</p><h2 className="mt-0.5 text-lg font-bold text-slate-900">Paso {step} de 4</h2>{restored?.draft && <p className="mt-1 text-[10px] font-semibold text-emerald-700">Borrador local recuperado</p>}</div><div className="flex items-center gap-1"><button onClick={() => { window.localStorage.removeItem(storageKey); setDraft(EMPTY_DRAFT); setStep(1) }} className="rounded-lg px-2 py-1.5 text-[10px] font-bold text-slate-500 hover:bg-slate-100">Descartar</button><button onClick={onClose} className="rounded-xl p-2 text-slate-400 hover:bg-slate-100"><X className="h-5 w-5" /></button></div></header>
        <div className="grid grid-cols-4 gap-1 bg-slate-100">{['Base', 'Destino', 'Anuncio', 'Revisión'].map((label, index) => <div key={label} className={cn('bg-white px-3 py-2 text-center text-[10px] font-bold', step >= index + 1 ? 'text-[#1A56DB]' : 'text-slate-400')}><div className={cn('mb-1 h-1 rounded-full', step >= index + 1 ? 'bg-[#1A56DB]' : 'bg-slate-200')} />{label}</div>)}</div>
        <div className="flex-1 overflow-y-auto p-5 sm:p-7">
          {step === 1 && <div className="grid gap-5 sm:grid-cols-2"><label className="sm:col-span-2"><span className={labelClass}>Nombre interno</span><input className={inputClass} value={draft.name} onChange={(event) => update('name', event.target.value)} placeholder="Ej. Lanzamiento Parque Norte · septiembre" /></label><label><span className={labelClass}>Cuenta publicitaria</span><select className={inputClass} value={draft.accountId} onChange={(event) => update('accountId', event.target.value)}><option value="">Seleccionar</option>{accounts.map((asset) => <option key={asset.id} value={asset.id}>{asset.display_name || asset.external_id}</option>)}</select></label><label><span className={labelClass}>Proyecto</span><select className={inputClass} value={draft.projectId} onChange={(event) => update('projectId', event.target.value)}><option value="">Seleccionar</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label><div className="rounded-2xl border border-blue-200 bg-blue-50 p-4 sm:col-span-2"><p className="flex items-center gap-2 text-xs font-bold text-blue-900"><ShieldCheck className="h-4 w-4" /> Categoría especial Housing</p><p className="mt-1 text-xs leading-5 text-blue-700">Se aplica obligatoriamente. La segmentación por edad, género o atributos sensibles no está disponible.</p></div></div>}
          {step === 2 && <div className="grid gap-5 sm:grid-cols-2"><label><span className={labelClass}>Objetivo</span><select className={inputClass} value={draft.objective} onChange={(event) => update('objective', event.target.value as CampaignDraft['objective'])}><option value="OUTCOME_LEADS">Generar leads</option><option value="OUTCOME_TRAFFIC">Tráfico al proyecto</option><option value="OUTCOME_ENGAGEMENT">Conversaciones</option></select></label><label><span className={labelClass}>Destino</span><select className={inputClass} value={draft.destination} onChange={(event) => { update('destination', event.target.value as CampaignDraft['destination']); update('destinationAssetId', event.target.value === 'website' ? '-1' : '') }}><option value="lead_form">Formulario instantáneo</option><option value="whatsapp">WhatsApp</option><option value="instagram">Instagram</option><option value="website">Sitio web</option></select></label><label><span className={labelClass}>Página corporativa</span><select className={inputClass} value={draft.pageId} onChange={(event) => { update('pageId', event.target.value); update('destinationAssetId', '') }}><option value="">Seleccionar</option>{pages.map((asset) => <option key={asset.id} value={asset.id}>{asset.display_name || asset.external_id}</option>)}</select></label><label><span className={labelClass}>Activo de destino</span><select className={inputClass} value={draft.destinationAssetId} onChange={(event) => update('destinationAssetId', event.target.value)}><option value="">Seleccionar</option>{destinationOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label><label><span className={labelClass}>Tipo de presupuesto</span><select className={inputClass} value={draft.budgetType} onChange={(event) => { update('budgetType', event.target.value as CampaignDraft['budgetType']); update('budget', '') }}><option value="daily">Diario</option><option value="lifetime">Total</option></select></label><label><span className={labelClass}>Presupuesto {policy.currency}</span><input type="number" min="1" max={limit} className={inputClass} value={draft.budget} onChange={(event) => update('budget', event.target.value)} placeholder={`Máximo ${money(limit, policy.currency)}`} /></label><label><span className={labelClass}>Inicio</span><input type="datetime-local" className={inputClass} value={draft.startAt} onChange={(event) => update('startAt', event.target.value)} /></label><label><span className={labelClass}>Término</span><input type="datetime-local" className={inputClass} value={draft.endAt} onChange={(event) => update('endAt', event.target.value)} /></label></div>}
          {step === 3 && <div className="grid gap-5 sm:grid-cols-2"><label className="sm:col-span-2"><span className={labelClass}>Texto principal</span><textarea rows={4} className={cn(inputClass, 'h-auto py-3')} value={draft.primaryText} onChange={(event) => update('primaryText', event.target.value)} placeholder="Describe el proyecto con información comprobable…" /></label><label><span className={labelClass}>Titular</span><input className={inputClass} value={draft.headline} onChange={(event) => update('headline', event.target.value)} /></label><label><span className={labelClass}>Llamado a la acción</span><select className={inputClass} value={draft.cta} onChange={(event) => update('cta', event.target.value)}><option value="LEARN_MORE">Más información</option><option value="SIGN_UP">Registrarte</option><option value="CONTACT_US">Contactar</option><option value="WHATSAPP_MESSAGE">Enviar WhatsApp</option></select></label><label className="sm:col-span-2"><span className={labelClass}>Descripción breve</span><input className={inputClass} value={draft.description} onChange={(event) => update('description', event.target.value)} /></label>{draft.destination === 'website' && <label className="sm:col-span-2"><span className={labelClass}>URL HTTPS del proyecto</span><input className={inputClass} value={draft.destinationUrl} onChange={(event) => update('destinationUrl', event.target.value)} placeholder="https://…" /></label>}<label><span className={labelClass}>Imagen pública HTTPS</span><input className={inputClass} value={draft.mediaUrl} onChange={(event) => update('mediaUrl', event.target.value)} placeholder="https://…" /></label><label><span className={labelClass}>Instagram corporativo (opcional)</span><select className={inputClass} value={draft.instagramId} onChange={(event) => update('instagramId', event.target.value)}><option value="">Sin Instagram</option>{instagrams.map((asset) => <option key={asset.id} value={asset.id}>{asset.display_name || asset.external_id}</option>)}</select></label><div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 sm:col-span-2"><p className="flex items-center gap-2 text-xs font-bold text-amber-900"><AlertTriangle className="h-4 w-4" /> Control de contenido</p><p className="mt-1 text-xs leading-5 text-amber-800">No uses “aprobación garantizada”, “sin DICOM” ni promesas de financiamiento. Jefatura revisará precio, inventario y condiciones.</p></div></div>}
          {step === 4 && <div className="grid gap-4 lg:grid-cols-[1fr_320px]"><div className="space-y-3"><h3 className="text-sm font-bold text-slate-900">Resumen para revisión</h3>{[['Campaña', draft.name], ['Proyecto', projects.find((item) => item.id === Number(draft.projectId))?.name || '—'], ['Destino', draft.destination], ['Presupuesto', `${money(Number(draft.budget), policy.currency)} · ${draft.budgetType === 'daily' ? 'diario' : 'total'}`], ['Segmentación', 'Chile · Advantage Audience · Housing']].map(([label, value]) => <div key={label} className="flex justify-between gap-4 rounded-xl border border-slate-200 px-3 py-2.5 text-xs"><span className="text-slate-500">{label}</span><span className="text-right font-semibold text-slate-800">{value}</span></div>)}<div className="rounded-xl bg-slate-50 p-3 text-xs leading-5 text-slate-600">Al guardar no se publica ni se activa gasto. El borrador debe enviarse a jefatura, publicarse pausado y activarse con una segunda confirmación.</div></div><div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="aspect-[1.5] bg-slate-100">{draft.mediaUrl ? <img src={draft.mediaUrl} alt="Vista previa" className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center text-xs text-slate-400">Vista previa de imagen</div>}</div><div className="p-4"><p className="text-[10px] font-semibold uppercase text-slate-400">Publicidad · Housing</p><p className="mt-1 text-sm font-bold text-slate-900">{draft.headline}</p><p className="mt-1 line-clamp-4 text-xs leading-5 text-slate-600">{draft.primaryText}</p><span className="mt-3 inline-flex rounded-lg bg-slate-100 px-3 py-2 text-[11px] font-bold text-slate-700">Más información</span></div></div></div>}
        </div>
        <footer className="flex items-center justify-between border-t border-slate-100 px-5 py-4 sm:px-7"><Button variant="ghost" disabled={step === 1 || saving} onClick={() => setStep((current) => Math.max(1, current - 1) as WizardStep)}>Anterior</Button>{step < 4 ? <Button onClick={next}>Continuar <ArrowRight className="ml-1.5 h-4 w-4" /></Button> : <Button disabled={saving} onClick={save}>{saving ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Check className="mr-1.5 h-4 w-4" />} Guardar borrador</Button>}</footer>
      </div>
    </div>
  )
}

function CampaignActions({ campaign, isAdmin, busy, onAction }: { campaign: MetaAdCampaign; isAdmin: boolean; busy: boolean; onAction: (action: 'submit' | 'approve' | 'reject' | 'publish' | 'activate' | 'pause') => void }) {
  return <div className="flex flex-wrap justify-end gap-1.5">{(['draft', 'rejected'].includes(campaign.status)) && <Button variant="outline" size="sm" disabled={busy} onClick={() => onAction('submit')}><Send className="mr-1 h-3.5 w-3.5" /> Enviar</Button>}{isAdmin && campaign.status === 'pending_review' && <><Button size="sm" disabled={busy} onClick={() => onAction('approve')}><Check className="mr-1 h-3.5 w-3.5" /> Aprobar</Button><Button variant="outline" size="sm" disabled={busy} onClick={() => onAction('reject')}>Rechazar</Button></>}{isAdmin && ['approved', 'partial_error'].includes(campaign.status) && <Button size="sm" disabled={busy} onClick={() => onAction('publish')}><Megaphone className="mr-1 h-3.5 w-3.5" /> Publicar pausada</Button>}{isAdmin && ['published_paused', 'paused'].includes(campaign.status) && <Button size="sm" disabled={busy} onClick={() => onAction('activate')}><Play className="mr-1 h-3.5 w-3.5" /> Activar gasto</Button>}{isAdmin && campaign.status === 'active' && <Button variant="outline" size="sm" disabled={busy} onClick={() => onAction('pause')}><Pause className="mr-1 h-3.5 w-3.5" /> Pausar</Button>}</div>
}

export function MetaAdsPage() {
  const user = useAuthStore((state) => state.user)
  const isAdmin = user?.role === 'admin'
  const [searchParams] = useSearchParams()
  const focusedCampaignId = Number(searchParams.get('campaign')) || null
  const [tab, setTab] = useState<Tab>('overview')
  const [assets, setAssets] = useState<MetaAsset[]>([])
  const [campaigns, setCampaigns] = useState<MetaAdCampaign[]>([])
  const [forms, setForms] = useState<MetaLeadForm[]>([])
  const [projects, setProjects] = useState<Array<{ id: number; name: string; status: string }>>([])
  const [users, setUsers] = useState<BrokerUser[]>([])
  const [conversions, setConversions] = useState<Array<{ id: number; event_name: string; status: string; last_error_code: string | null; sent_at: string | null; created_at: string }>>([])
  const [policy, setPolicy] = useState<MetaAdsPolicy | null>(null)
  const [analytics, setAnalytics] = useState<MetaAdsAnalytics | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [wizardOpen, setWizardOpen] = useState(false)
  const [policyDraft, setPolicyDraft] = useState({ daily: '', lifetime: '' })
  const [expandedForm, setExpandedForm] = useState<number | null>(null)
  const [reviewCampaign, setReviewCampaign] = useState<MetaAdCampaign | null>(null)
  const [activationCampaign, setActivationCampaign] = useState<MetaAdCampaign | null>(null)
  const [drilldown, setDrilldown] = useState<{ label: string; outcome: 'lead' | 'advised' | 'meeting' | 'reservation' | 'sale'; campaign_external_id?: string } | null>(null)
  const [drilldownItems, setDrilldownItems] = useState<Array<{ id: number; name: string | null; phone: string | null; pipeline_stage: string | null }>>([])
  const [drilldownTotal, setDrilldownTotal] = useState(0)
  const [drilldownLoading, setDrilldownLoading] = useState(false)
  const today = new Date().toISOString().slice(0, 10)
  const prior = new Date(Date.now() - 30 * 86_400_000).toISOString().slice(0, 10)
  const [analyticsFilters, setAnalyticsFilters] = useState<{ date_from: string; date_to: string; account_external_id?: string; campaign_external_id?: string; project_id?: number; executive_id?: number }>({ date_from: prior, date_to: today })

  const load = useCallback(async () => {
    setIsLoading(true)
    try {
      const [assetResult, campaignResult, formResult, policyResult, analyticsResult, projectResult, userResult, conversionResult] = await Promise.all([
        metaService.adsAssets(), metaService.adCampaigns(), metaService.leadForms(), metaService.adsPolicy(),
        metaService.adsAnalytics({ date_from: prior, date_to: today }),
        metaService.adsProjects(),
        isAdmin ? metaService.users() : Promise.resolve([]),
        isAdmin ? metaService.conversionDiagnostics() : Promise.resolve([]),
      ])
      setAssets(assetResult); setCampaigns(campaignResult); setForms(formResult); setPolicy(policyResult); setAnalytics(analyticsResult); setProjects(projectResult); setUsers(userResult.filter((item) => item.is_active && item.role.toLowerCase() === 'agent')); setConversions(conversionResult)
      setPolicyDraft({ daily: String(policyResult.max_daily_budget || ''), lifetime: String(policyResult.max_lifetime_budget || '') })
    } catch (error) { toast.error(getErrorMessage(error)) } finally { setIsLoading(false) }
  }, [isAdmin, prior, today])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (!focusedCampaignId || !campaigns.some((campaign) => campaign.id === focusedCampaignId)) return
    setTab('campaigns')
    window.setTimeout(() => document.getElementById(`meta-campaign-${focusedCampaignId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 80)
  }, [campaigns, focusedCampaignId])
  useWebSocketEvent(useCallback((event) => { if (event.type.startsWith('meta_ad_campaign_')) load() }, [load]))

  const act = async (campaign: MetaAdCampaign, action: 'submit' | 'approve' | 'reject' | 'publish' | 'activate' | 'pause', comment?: string) => {
    if (action === 'publish' && !window.confirm('La campaña se creará en Meta completamente pausada. ¿Continuar?')) return
    setBusyId(campaign.id)
    try {
      const updated = action === 'activate' ? await metaService.activateAdCampaign(campaign.id, campaign.version)
        : action === 'pause' ? await metaService.pauseAdCampaign(campaign.id, campaign.version)
          : await metaService.transitionAdCampaign(campaign.id, action, campaign.version, comment)
      setCampaigns((current) => current.map((item) => item.id === updated.id ? updated : item))
      if (action === 'approve' || action === 'reject') setReviewCampaign(null)
      if (action === 'activate') setActivationCampaign(null)
      toast.success(action === 'submit' ? 'Campaña enviada a revisión' : action === 'approve' ? 'Campaña aprobada' : action === 'publish' ? 'Campaña publicada en pausa' : action === 'activate' ? 'Campaña activada' : action === 'pause' ? 'Campaña pausada' : 'Campaña rechazada')
    } catch (error) { toast.error(getErrorMessage(error)); await load() } finally { setBusyId(null) }
  }

  const requestCampaignAction = (campaign: MetaAdCampaign, action: 'submit' | 'approve' | 'reject' | 'publish' | 'activate' | 'pause') => {
    if (action === 'approve' || action === 'reject') return setReviewCampaign(campaign)
    if (action === 'activate') return setActivationCampaign(campaign)
    void act(campaign, action)
  }

  const savePolicy = async () => {
    if (!policy) return
    try {
      const updated = await metaService.updateAdsPolicy({ ...policy, max_daily_budget: Number(policyDraft.daily), max_lifetime_budget: Number(policyDraft.lifetime), expected_version: policy.version })
      setPolicy(updated); toast.success('Límites de gasto actualizados')
    } catch (error) { toast.error(getErrorMessage(error)) }
  }

  const sync = async (kind: 'forms' | 'insights') => {
    try { kind === 'forms' ? await metaService.syncLeadForms() : await metaService.syncAdsInsights(); toast.success('Sincronización enviada al worker') } catch (error) { toast.error(getErrorMessage(error)) }
  }

  const saveFormResult = (updated: MetaLeadForm) => {
    setForms((current) => current.map((item) => item.id === updated.id ? updated : item))
    setExpandedForm(null)
  }

  const openDrilldown = async (next: NonNullable<typeof drilldown>) => {
    setDrilldown(next)
    setDrilldownLoading(true)
    try {
      const response = await metaService.adsAnalyticsLeads({ ...analyticsFilters, outcome: next.outcome, campaign_external_id: next.campaign_external_id || analyticsFilters.campaign_external_id, limit: 100 })
      setDrilldownItems(response.items)
      setDrilldownTotal(response.total)
    } catch (error) {
      toast.error(getErrorMessage(error))
      setDrilldownItems([])
      setDrilldownTotal(0)
    } finally {
      setDrilldownLoading(false)
    }
  }

  const applyAnalyticsFilters = async () => {
    try {
      setAnalytics(await metaService.adsAnalytics(analyticsFilters))
    } catch (error) {
      toast.error(getErrorMessage(error))
    }
  }

  const kpis = analytics?.kpis
  const maxTrend = Math.max(...(analytics?.trend.map((point) => point.spend) || [0]), 1)
  const accountCount = assets.filter((asset) => asset.asset_type === 'ad_account' && asset.status === 'active').length
  const canDraft = user?.role !== 'superadmin' && !!policy && policy.max_daily_budget > 0 && policy.max_lifetime_budget > 0 && accountCount > 0
  const campaignNames = useMemo(() => new Map(campaigns.filter((item) => item.external_id).map((item) => [item.external_id, item.name])), [campaigns])

  if (isLoading) return <div className="flex min-h-[75vh] items-center justify-center"><LoadingSpinner size="lg" /></div>

  return <div className="min-h-full bg-[linear-gradient(180deg,#F5F8FD_0%,#FFFFFF_400px)] p-4 sm:p-8"><div className="mx-auto max-w-[1500px]"><PageHeader title="Meta Ads" description="Publicidad pagada separada de las automatizaciones CRM, con aprobación y control de gasto." actions={<><Button variant="outline" size="sm" onClick={load}><RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Actualizar</Button><Button size="sm" disabled={!canDraft} onClick={() => setWizardOpen(true)}><Plus className="mr-1.5 h-4 w-4" /> Nueva campaña</Button></>} />
    {!canDraft && <div className="mb-5 flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-900"><AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" /><div><p className="text-sm font-bold">Publicidad todavía no disponible</p><p className="mt-0.5 text-xs leading-5">Jefatura debe conectar una cuenta publicitaria corporativa y definir límites de presupuesto antes de crear borradores.</p></div></div>}
    <nav className="mb-5 flex gap-1 overflow-x-auto rounded-xl border border-[#DDE6F2] bg-white p-1 shadow-sm">{([['overview', 'Resultados', BarChart3], ['campaigns', 'Campañas', Megaphone], ['forms', 'Formularios', FormInput], ...(isAdmin ? [['conversions', 'Conversiones', Gauge] as const, ['policy', 'Control de gasto', ShieldCheck] as const] : [])] as Array<[Tab, string, typeof BarChart3]>).map(([id, label, Icon]) => <button key={id} onClick={() => setTab(id)} className={cn('flex h-9 items-center gap-2 whitespace-nowrap rounded-lg px-3 text-xs font-bold transition', tab === id ? 'bg-[#EBF2FF] text-[#1A56DB]' : 'text-slate-500 hover:bg-slate-50')}><Icon className="h-3.5 w-3.5" />{label}</button>)}</nav>

    {tab === 'overview' && <><section className="mb-4 rounded-2xl border border-[#DDE6F2] bg-white p-4 shadow-sm"><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6"><input aria-label="Desde" type="date" className={inputClass} value={analyticsFilters.date_from} onChange={(event) => setAnalyticsFilters((current) => ({ ...current, date_from: event.target.value }))} /><input aria-label="Hasta" type="date" className={inputClass} value={analyticsFilters.date_to} onChange={(event) => setAnalyticsFilters((current) => ({ ...current, date_to: event.target.value }))} /><select aria-label="Cuenta publicitaria" className={inputClass} value={analyticsFilters.account_external_id || ''} onChange={(event) => setAnalyticsFilters((current) => ({ ...current, account_external_id: event.target.value || undefined }))}><option value="">Todas las cuentas</option>{assets.filter((asset) => asset.asset_type === 'ad_account').map((asset) => <option key={asset.id} value={asset.external_id}>{asset.display_name || asset.external_id}</option>)}</select><select aria-label="Campaña" className={inputClass} value={analyticsFilters.campaign_external_id || ''} onChange={(event) => setAnalyticsFilters((current) => ({ ...current, campaign_external_id: event.target.value || undefined }))}><option value="">Todas las campañas</option>{campaigns.filter((campaign) => campaign.external_id).map((campaign) => <option key={campaign.id} value={campaign.external_id || ''}>{campaign.name}</option>)}</select><select aria-label="Proyecto" className={inputClass} value={analyticsFilters.project_id || ''} onChange={(event) => setAnalyticsFilters((current) => ({ ...current, project_id: event.target.value ? Number(event.target.value) : undefined }))}><option value="">Todos los proyectos</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select>{isAdmin ? <select aria-label="Ejecutivo" className={inputClass} value={analyticsFilters.executive_id || ''} onChange={(event) => setAnalyticsFilters((current) => ({ ...current, executive_id: event.target.value ? Number(event.target.value) : undefined }))}><option value="">Todo el equipo</option>{users.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}</select> : <Button onClick={applyAnalyticsFilters}>Aplicar filtros</Button>}</div>{isAdmin && <div className="mt-3 flex justify-end"><Button size="sm" onClick={applyAnalyticsFilters}>Aplicar filtros</Button></div>}</section><div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-8">{([
      ['Inversión', money(kpis?.spend, policy?.currency), CircleDollarSign, null], ['Impresiones', compact(kpis?.impressions || 0), Eye, null], ['Clics', compact(kpis?.clicks || 0), MousePointerClick, null], ['Leads CRM', kpis?.crm_leads || 0, Users, 'lead'], ['Asesorados', kpis?.advised || 0, Sparkles, 'advised'], ['Reuniones', kpis?.meetings || 0, Gauge, 'meeting'], ['Reservas', kpis?.reservations || 0, FileInput, 'reservation'], ['Ventas', kpis?.sales || 0, Check, 'sale'],
    ] as Array<[string, string | number, typeof BarChart3, NonNullable<typeof drilldown>['outcome'] | null]>).map(([label, value, Icon, outcome]) => <button type="button" key={label} disabled={!outcome} onClick={() => outcome && openDrilldown({ label, outcome })} className={cn('rounded-2xl border border-[#DDE6F2] bg-white p-3.5 text-left shadow-[0_6px_22px_rgba(30,64,175,0.05)]', outcome && 'transition hover:-translate-y-0.5 hover:border-blue-300 hover:shadow-md')}><div className="flex items-center justify-between"><span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</span><Icon className="h-3.5 w-3.5 text-[#1A56DB]" /></div><p className="mt-2 text-lg font-bold text-slate-900">{value}</p>{outcome && <p className="mt-1 text-[9px] font-semibold text-blue-600">Ver leads</p>}</button>)}</div>
    <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]"><section className="rounded-2xl border border-[#DDE6F2] bg-white p-5 shadow-sm"><div className="flex items-center justify-between"><div><h2 className="text-sm font-bold text-slate-900">Inversión diaria</h2><p className="mt-0.5 text-xs text-slate-500">Período seleccionado · datos sincronizados desde Meta</p></div>{isAdmin && <Button variant="outline" size="sm" onClick={() => sync('insights')}><RefreshCw className="mr-1 h-3.5 w-3.5" /> Sincronizar</Button>}</div>{analytics?.partial_sync && <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-[11px] font-semibold text-amber-800">Hay una sincronización parcial; los totales pueden cambiar.</p>}<div className="mt-5 flex h-48 items-end gap-1.5">{analytics?.trend.length ? analytics.trend.map((point) => <div key={point.date} className="group flex h-full min-w-1 flex-1 items-end"><div title={`${point.date}: ${money(point.spend, policy?.currency)}`} style={{ height: `${Math.max(3, point.spend / maxTrend * 100)}%` }} className="w-full rounded-t bg-[#1A56DB] transition hover:bg-blue-700" /></div>) : <div className="flex w-full items-center justify-center text-xs text-slate-400">Sin inversión sincronizada</div>}</div><div className="mt-3 flex justify-between text-[10px] text-slate-400"><span>{analyticsFilters.date_from}</span><span>{analyticsFilters.date_to}</span></div></section><section className="rounded-2xl border border-[#DDE6F2] bg-white p-5 shadow-sm"><h2 className="text-sm font-bold text-slate-900">Costo por resultado CRM</h2><p className="mt-0.5 text-xs text-slate-500">El guion indica ausencia de resultado, no costo cero.</p><div className="mt-4 divide-y divide-slate-100">{[['Conversación', kpis?.cost_per_conversation], ['Lead', kpis?.cost_per_lead], ['Asesoría', kpis?.cost_per_advised], ['Reunión', kpis?.cost_per_meeting], ['Reserva', kpis?.cost_per_reservation], ['Venta', kpis?.cost_per_sale]].map(([label, value]) => <div key={String(label)} className="flex items-center justify-between py-2.5 text-xs"><span className="text-slate-500">{label as string}</span><span className="font-bold text-slate-900">{money(value as number | null, policy?.currency)}</span></div>)}</div></section></div>
    <section className="mt-4 overflow-hidden rounded-2xl border border-[#DDE6F2] bg-white shadow-sm"><header className="border-b border-slate-100 px-5 py-4"><h2 className="text-sm font-bold text-slate-900">Rendimiento por campaña</h2></header>{analytics?.campaigns.length ? <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-xs"><thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Campaña</th><th className="px-4 py-3">Inversión</th><th className="px-4 py-3">Impresiones</th><th className="px-4 py-3">Clics</th><th className="px-4 py-3">Leads Meta</th></tr></thead><tbody>{analytics.campaigns.map((row) => <tr key={row.campaign_external_id} className="border-t border-slate-100"><td className="px-5 py-3 font-semibold text-slate-900">{campaignNames.get(row.campaign_external_id) || row.campaign_external_id}</td><td className="px-4 py-3">{money(row.spend, policy?.currency)}</td><td className="px-4 py-3">{compact(row.impressions)}</td><td className="px-4 py-3">{row.clicks}</td><td className="px-4 py-3"><button className="font-bold text-[#1A56DB] hover:underline" onClick={() => openDrilldown({ label: campaignNames.get(row.campaign_external_id) || 'Leads de campaña', outcome: 'lead', campaign_external_id: row.campaign_external_id })}>{row.leads} · ver</button></td></tr>)}</tbody></table></div> : <EmptyState title="Sin métricas por campaña" description="Los datos aparecerán después de la primera sincronización de Insights." />}</section></>}

    {tab === 'campaigns' && <section className="overflow-hidden rounded-2xl border border-[#DDE6F2] bg-white shadow-sm"><header className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><div><h2 className="text-sm font-bold text-slate-900">Campañas publicitarias</h2><p className="mt-0.5 text-xs text-slate-500">No incluye campañas internas ni referidos.</p></div><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600">{campaigns.length}</span></header>{campaigns.length ? <div className="divide-y divide-slate-100">{campaigns.map((campaign) => <article id={`meta-campaign-${campaign.id}`} key={campaign.id} className={cn('grid gap-3 px-5 py-4 transition lg:grid-cols-[1fr_180px_150px_330px] lg:items-center', focusedCampaignId === campaign.id && 'bg-blue-50 ring-1 ring-inset ring-blue-200')}><div><div className="flex flex-wrap items-center gap-2"><p className="text-sm font-bold text-slate-900">{campaign.name}</p><span className={cn('rounded-full px-2 py-0.5 text-[10px] font-bold', STATUS[campaign.status].className)}>{STATUS[campaign.status].label}</span></div><p className="mt-1 text-xs text-slate-500">{campaign.destination_type} · Housing · v{campaign.version}</p>{campaign.rejection_comment && <p className="mt-1 text-[11px] font-medium text-rose-600">Motivo: {campaign.rejection_comment}</p>}{campaign.last_error_detail && <p className="mt-1 text-[11px] font-medium text-rose-600">{campaign.last_error_detail}</p>}</div><div className="text-xs"><p className="text-slate-400">Presupuesto</p><p className="mt-0.5 font-bold text-slate-900">{money(campaign.daily_budget || campaign.lifetime_budget, campaign.currency)} <span className="font-medium text-slate-400">{campaign.daily_budget ? '/ día' : 'total'}</span></p></div><div className="text-xs"><p className="text-slate-400">Creada</p><p className="mt-0.5 font-semibold text-slate-700">{new Date(campaign.created_at).toLocaleDateString('es-CL')}</p></div><CampaignActions campaign={campaign} isAdmin={isAdmin} busy={busyId === campaign.id} onAction={(action) => requestCampaignAction(campaign, action)} /></article>)}</div> : <EmptyState icon={Megaphone} title="No hay campañas Meta" description="Crea un borrador; no se activará gasto hasta completar las dos aprobaciones." action={canDraft ? { label: 'Nueva campaña', onClick: () => setWizardOpen(true) } : undefined} />}</section>}

    {tab === 'forms' && <section className="overflow-hidden rounded-2xl border border-[#DDE6F2] bg-white shadow-sm"><header className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><div><h2 className="text-sm font-bold text-slate-900">Formularios de Lead Ads</h2><p className="mt-0.5 text-xs text-slate-500">Mapea preguntas a campos CRM, revisa el resultado normalizado y recién entonces guarda.</p></div>{isAdmin && <Button variant="outline" size="sm" onClick={() => sync('forms')}><RefreshCw className="mr-1 h-3.5 w-3.5" /> Sincronizar</Button>}</header>{forms.length ? <div className="divide-y divide-slate-100">{forms.map((form) => <article key={form.id} className="px-5 py-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><div className="flex items-center gap-2"><p className="text-sm font-bold text-slate-900">{form.name}</p><span className={cn('rounded-full px-2 py-0.5 text-[10px] font-bold', form.status === 'active' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500')}>{form.status}</span></div><p className="mt-1 text-xs text-slate-500">{form.questions.length} preguntas · {Object.keys(form.field_mapping).length ? 'Mapeo configurado' : 'Sin mapear'}</p></div>{isAdmin && <Button variant="outline" size="sm" onClick={() => setExpandedForm((current) => current === form.id ? null : form.id)}>{expandedForm === form.id ? 'Cerrar' : 'Configurar'}</Button>}</div>{expandedForm === form.id && <LeadFormEditor form={form} projects={projects} onSaved={saveFormResult} />}</article>)}</div> : <EmptyState icon={FormInput} title="Sin formularios sincronizados" description="Conecta una página corporativa con formularios activos y ejecuta la sincronización." />}</section>}

    {tab === 'conversions' && isAdmin && <section className="overflow-hidden rounded-2xl border border-[#DDE6F2] bg-white shadow-sm"><header className="border-b border-slate-100 px-5 py-4"><h2 className="text-sm font-bold text-slate-900">Diagnóstico de Conversions API</h2><p className="mt-1 text-xs text-slate-500">No muestra teléfonos, correos ni payloads. La función permanece desactivada hasta configurar consentimiento.</p></header>{conversions.length ? <div className="divide-y divide-slate-100">{conversions.map((event) => <div key={event.id} className="grid gap-2 px-5 py-3.5 text-xs sm:grid-cols-[1fr_130px_180px]"><div><p className="font-bold text-slate-900">{event.event_name}</p>{event.last_error_code && <p className="mt-1 font-semibold text-rose-600">{event.last_error_code}</p>}</div><span className={cn('w-fit rounded-full px-2.5 py-1 text-[10px] font-bold', event.status === 'sent' ? 'bg-emerald-50 text-emerald-700' : event.status === 'failed' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700')}>{event.status}</span><span className="text-slate-500">{new Date(event.sent_at || event.created_at).toLocaleString('es-CL')}</span></div>)}</div> : <EmptyState title="Sin conversiones enviadas" description="Es el estado esperado mientras Conversions API esté desactivada o no exista consentimiento válido." />}</section>}

    {tab === 'policy' && isAdmin && policy && <section className="max-w-2xl rounded-2xl border border-[#DDE6F2] bg-white p-5 shadow-sm"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-[#1A56DB]"><ShieldCheck className="h-5 w-5" /></div><h2 className="mt-4 text-base font-bold text-slate-900">Política de presupuesto</h2><p className="mt-1 text-xs leading-5 text-slate-500">Estos límites se validan otra vez en el servidor. Aumentarlos queda auditado y no activa campañas existentes.</p><div className="mt-5 grid gap-4 sm:grid-cols-2"><label><span className={labelClass}>Máximo diario · {policy.currency}</span><input type="number" min="0" className={inputClass} value={policyDraft.daily} onChange={(event) => setPolicyDraft((current) => ({ ...current, daily: event.target.value }))} /></label><label><span className={labelClass}>Máximo total · {policy.currency}</span><input type="number" min="0" className={inputClass} value={policyDraft.lifetime} onChange={(event) => setPolicyDraft((current) => ({ ...current, lifetime: event.target.value }))} /></label></div><label className="mt-4 flex items-center gap-2 text-xs font-semibold text-slate-700"><input type="checkbox" checked={policy.require_budget_increase_confirmation} onChange={(event) => setPolicy({ ...policy, require_budget_increase_confirmation: event.target.checked })} className="h-4 w-4 accent-[#1A56DB]" /> Confirmar aumentos de presupuesto</label><Button className="mt-5" onClick={savePolicy}>Guardar límites</Button></section>}
    {wizardOpen && policy && <Wizard assets={assets} forms={forms} projects={projects} policy={policy} storageKey={`meta-ad-draft:${user?.broker_id || 0}:${user?.id || 0}`} onClose={() => setWizardOpen(false)} onSaved={(campaign) => { setCampaigns((current) => [campaign, ...current]); setWizardOpen(false); setTab('campaigns') }} />}
    {reviewCampaign && <CampaignReviewModal campaign={reviewCampaign} busy={busyId === reviewCampaign.id} onClose={() => setReviewCampaign(null)} onDecision={(decision, comment) => void act(reviewCampaign, decision, comment)} />}
    {activationCampaign && <ActivationModal campaign={activationCampaign} accountName={assets.find((asset) => asset.id === activationCampaign.ad_account_asset_id)?.display_name || `Cuenta ${activationCampaign.ad_account_asset_id}`} busy={busyId === activationCampaign.id} onClose={() => setActivationCampaign(null)} onActivate={() => void act(activationCampaign, 'activate')} />}
    {drilldown && <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/45 p-0 backdrop-blur-[2px] sm:items-center sm:p-6" onMouseDown={(event) => { if (event.target === event.currentTarget) setDrilldown(null) }}><div className="flex max-h-[82vh] w-full max-w-xl flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl sm:rounded-3xl"><header className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><div><p className="text-[10px] font-bold uppercase tracking-wide text-[#1A56DB]">Resultado trazable</p><h2 className="mt-1 text-base font-bold text-slate-900">{drilldown.label}</h2><p className="mt-0.5 text-xs text-slate-500">{drilldownTotal} leads en el período</p></div><button className="rounded-xl p-2 text-slate-400 hover:bg-slate-100" onClick={() => setDrilldown(null)}><X className="h-5 w-5" /></button></header><div className="flex-1 overflow-y-auto">{drilldownLoading ? <div className="flex justify-center py-20"><LoadingSpinner /></div> : drilldownItems.length ? <div className="divide-y divide-slate-100">{drilldownItems.map((lead) => <Link key={lead.id} to={`/leads?lead=${lead.id}`} className="flex items-center justify-between gap-4 px-5 py-3.5 hover:bg-slate-50"><div className="min-w-0"><p className="truncate text-sm font-bold text-slate-900">{lead.name || lead.phone || `Lead #${lead.id}`}</p><p className="mt-0.5 text-xs text-slate-500">{lead.phone || 'Identidad de canal Meta'}</p></div><span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">{lead.pipeline_stage || 'entrada'}</span></Link>)}</div> : <EmptyState title="Sin leads" description="No hay leads que compongan este indicador en el período seleccionado." />}</div></div></div>}
  </div></div>
}
