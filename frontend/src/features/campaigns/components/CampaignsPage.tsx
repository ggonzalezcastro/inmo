import { useState, useEffect, useCallback } from 'react'
import {
  Plus, Trash2, MessageSquare, Phone, ArrowRight, Clock,
  Zap, Loader2, Send, Pause, Play, CheckCircle,
  X, AlertCircle, Users, Sparkles, RefreshCw, Megaphone,
  TrendingUp, Activity, Target,
} from 'lucide-react'
import { toast } from 'sonner'
import { LoadingSpinner } from '@/shared/components/common/LoadingSpinner'
import { getErrorMessage } from '@/shared/types/api'
import { usePermissions } from '@/shared/hooks/usePermissions'
import {
  campaignsService,
  type Campaign,
  type CampaignStep,
  type CampaignChannel,
  type CampaignStatus,
  type CampaignTrigger,
  type StepAction,
  type CreateStepDto,
} from '../services/campaigns.service'

// ── Design tokens (light system theme) ────────────────────────────────────────
const BLUE      = '#1A56DB'
const BLUE_LIGHT = '#EBF2FF'
const BLUE_BORDER = '#BFCFFF'
const BORDER    = '#E2EAF4'
const BORDER2   = '#D1D9E6'
const BG        = '#F8FAFC'
const SURFACE   = '#FFFFFF'
const TEXT      = '#111827'
const TEXT2     = '#374151'
const MUTED     = '#6B7280'
const PLACEHOLDER = '#9CA3AF'

// ── Status config ─────────────────────────────────────────────────────────────
const STATUS_CONFIG: Record<CampaignStatus, { label: string; dot: string; bg: string; text: string; border: string }> = {
  draft:          { label: 'Borrador',   dot: '#9CA3AF', bg: '#F3F4F6', text: '#374151', border: '#D1D5DB' },
  pending_review: { label: 'En revisión', dot: '#D97706', bg: '#FEF3C7', text: '#92400E', border: '#FCD34D' },
  active:         { label: 'Activa',     dot: '#059669', bg: '#D1FAE5', text: '#065F46', border: '#6EE7B7' },
  paused:         { label: 'Pausada',    dot: '#EA580C', bg: '#FFEDD5', text: '#7C2D12', border: '#FDBA74' },
  completed:      { label: 'Completada', dot: BLUE,      bg: BLUE_LIGHT, text: '#1E3A8A', border: BLUE_BORDER },
}

function StatusBadge({ status }: { status: CampaignStatus }) {
  const s = STATUS_CONFIG[status] ?? STATUS_CONFIG.draft
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border"
      style={{ background: s.bg, color: s.text, borderColor: s.border }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full shrink-0"
        style={{ background: s.dot, boxShadow: status === 'active' ? `0 0 0 2px ${s.dot}33` : 'none' }}
      />
      {s.label}
    </span>
  )
}

// ── Step type config ──────────────────────────────────────────────────────────
const STEP_TYPES: Record<StepAction, { label: string; icon: React.FC<{ className?: string }>; color: string; bg: string; border: string }> = {
  send_message:     { label: 'Enviar mensaje', icon: MessageSquare, color: '#1A56DB', bg: '#EBF2FF', border: '#BFCFFF' },
  make_call:        { label: 'Llamada',         icon: Phone,         color: '#059669', bg: '#D1FAE5', border: '#6EE7B7' },
  update_stage:     { label: 'Cambiar etapa',   icon: ArrowRight,    color: '#7C3AED', bg: '#EDE9FE', border: '#C4B5FD' },
  schedule_meeting: { label: 'Agendar cita',    icon: CheckCircle,   color: '#D97706', bg: '#FEF3C7', border: '#FCD34D' },
}

const CHANNELS: { value: CampaignChannel; label: string }[] = [
  { value: 'whatsapp',  label: 'WhatsApp'  },
  { value: 'call',      label: 'Llamada'   },
  { value: 'email',     label: 'Email'     },
]

const TRIGGERS: { value: CampaignTrigger; label: string; desc: string }[] = [
  { value: 'manual',       label: 'Manual',       desc: 'Aplicar a leads manualmente'        },
  { value: 'inactivity',   label: 'Inactividad',  desc: 'Lead sin contacto por N días'       },
  { value: 'lead_score',   label: 'Score',        desc: 'Cuando el score entra en un rango'  },
  { value: 'stage_change', label: 'Etapa',        desc: 'Al cambiar de etapa en el pipeline' },
]

const STAGES = ['entrada','perfilamiento','calificacion_financiera','potencial','agendado','ganado','perdido']

// ── TriggerConfig ─────────────────────────────────────────────────────────────
function TriggerConfig({
  trigger, condition, onChange,
}: {
  trigger: CampaignTrigger
  condition: Record<string, unknown>
  onChange: (t: CampaignTrigger, c: Record<string, unknown>) => void
}) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        {TRIGGERS.map(t => (
          <button
            key={t.value}
            type="button"
            onClick={() => onChange(t.value, {})}
            className={`flex flex-col items-start gap-0.5 p-3 rounded-xl border text-left transition-all ${
              trigger === t.value
                ? 'border-[#BFCFFF] bg-[#EBF2FF]'
                : 'border-[#E2EAF4] bg-white hover:border-[#BFCFFF] hover:bg-[#F5F8FF]'
            }`}
          >
            <span className={`text-xs font-semibold ${trigger === t.value ? 'text-[#1A56DB]' : 'text-[#374151]'}`}>{t.label}</span>
            <span className="text-[10px] text-[#9CA3AF]">{t.desc}</span>
          </button>
        ))}
      </div>

      {trigger === 'inactivity' && (
        <div className="flex items-center gap-2 p-3 rounded-xl border border-[#E2EAF4] bg-[#F8FAFC]">
          <span className="text-xs text-[#6B7280]">Si el lead lleva más de</span>
          <input
            type="number" min={1}
            value={(condition.inactivity_days as number) ?? 7}
            onChange={e => onChange(trigger, { inactivity_days: parseInt(e.target.value) || 7 })}
            className="w-14 bg-white text-xs text-[#111827] border border-[#D1D9E6] rounded-lg px-2 py-1 text-center outline-none focus:border-[#1A56DB] transition-colors"
          />
          <span className="text-xs text-[#6B7280]">días sin contacto</span>
        </div>
      )}

      {trigger === 'lead_score' && (
        <div className="flex items-center gap-2 p-3 rounded-xl border border-[#E2EAF4] bg-[#F8FAFC]">
          <span className="text-xs text-[#6B7280]">Score entre</span>
          <input type="number" min={0} max={100}
            value={(condition.score_min as number) ?? 0}
            onChange={e => onChange(trigger, { ...condition, score_min: parseInt(e.target.value) || 0 })}
            className="w-14 bg-white text-xs text-[#111827] border border-[#D1D9E6] rounded-lg px-2 py-1 text-center outline-none focus:border-[#1A56DB] transition-colors"
          />
          <span className="text-xs text-[#6B7280]">y</span>
          <input type="number" min={0} max={100}
            value={(condition.score_max as number) ?? 100}
            onChange={e => onChange(trigger, { ...condition, score_max: parseInt(e.target.value) || 100 })}
            className="w-14 bg-white text-xs text-[#111827] border border-[#D1D9E6] rounded-lg px-2 py-1 text-center outline-none focus:border-[#1A56DB] transition-colors"
          />
        </div>
      )}

      {trigger === 'stage_change' && (
        <div className="flex items-center gap-2 p-3 rounded-xl border border-[#E2EAF4] bg-[#F8FAFC]">
          <span className="text-xs text-[#6B7280]">Al entrar en etapa</span>
          <select
            value={(condition.stage as string) ?? ''}
            onChange={e => onChange(trigger, { stage: e.target.value })}
            className="flex-1 bg-white text-xs text-[#111827] border border-[#D1D9E6] rounded-lg px-2 py-1.5 outline-none focus:border-[#1A56DB] transition-colors"
          >
            <option value="">Seleccionar…</option>
            {STAGES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      )}
    </div>
  )
}

// ── SavedStepRow (read-only / editable) ───────────────────────────────────────
function SavedStepRow({
  step, index, onDelete, onSaved,
}: {
  step: CampaignStep
  index: number
  onDelete: () => void
  onSaved: (updated: CampaignStep) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<Partial<CampaignStepCreate>>({})
  const [saving, setSaving] = useState(false)

  const handleEdit = () => {
    setDraft({
      action: step.action as StepAction,
      delay_hours: step.delay_hours,
      message_text: step.message_text ?? '',
      use_ai_message: step.use_ai_message,
      channel: step.channel as CampaignChannel | undefined,
    })
    setEditing(true)
  }

  const handleSave = async () => {
    if (!step.campaign_id) return
    setSaving(true)
    try {
      const updated = await campaignsService.updateStep(step.campaign_id, step.id, draft)
      onSaved(updated)
      setEditing(false)
    } catch {
      // keep editing open on error
    } finally {
      setSaving(false)
    }
  }

  if (editing) {
    return (
      <div>
        <StepCard
          step={{ ...draft, _localId: String(step.id) } as LocalStep}
          index={index}
          campaignId={step.campaign_id}
          onDelete={() => { setEditing(false) }}
          onChange={changes => setDraft(prev => ({ ...prev, ...changes }))}
        />
        <div className="flex gap-2 justify-end mb-3 -mt-2 pr-1">
          <button
            onClick={() => setEditing(false)}
            className="text-xs px-3 py-1.5 rounded-lg border transition-colors hover:bg-gray-50"
            style={{ borderColor: BORDER2, color: MUTED }}
          >
            Cancelar
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="text-xs px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-colors"
            style={{ background: BLUE, color: '#fff' }}
          >
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
            Guardar
          </button>
        </div>
      </div>
    )
  }

  const cfg = STEP_TYPES[step.action as StepAction] ?? STEP_TYPES.send_message
  const Icon = cfg.icon
  return (
    <div className="flex gap-3 items-start">
      <div className="flex flex-col items-center pt-3 shrink-0">
        <span
          className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold border"
          style={{ background: cfg.bg, color: cfg.color, borderColor: cfg.border }}
        >
          {index + 1}
        </span>
        <div className="w-px flex-1 min-h-[16px] mt-1" style={{ background: BORDER }} />
      </div>
      <div
        className="flex-1 flex items-center justify-between gap-3 px-4 py-3 mb-1 rounded-xl border bg-white cursor-pointer group transition-colors hover:border-[#1A56DB]"
        style={{ borderColor: BORDER2 }}
        onClick={handleEdit}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0" style={{ background: cfg.bg }}>
            <Icon className="w-3.5 h-3.5" style={{ color: cfg.color }} />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-semibold" style={{ color: TEXT }}>{cfg.label}</p>
            <p className="text-[10px] truncate" style={{ color: MUTED }}>
              {step.use_ai_message ? 'Mensaje generado por IA' : step.message_text ? `"${step.message_text.slice(0, 40)}…"` : ''}
              {step.delay_hours > 0 ? ` · esperar ${step.delay_hours}h` : ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <span className="text-[10px] opacity-0 group-hover:opacity-100 transition-opacity font-medium" style={{ color: BLUE }}>Editar</span>
          <button
            onClick={e => { e.stopPropagation(); onDelete() }}
            className="w-6 h-6 rounded-md flex items-center justify-center transition-colors hover:bg-red-50 hover:text-red-500"
            style={{ color: PLACEHOLDER }}
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  )
}

// ── StepCard (editable) ───────────────────────────────────────────────────────
function StepCard({
  step, index, campaignId, onDelete, onChange,
}: {
  step: CreateStepDto & { _localId: string }
  index: number
  campaignId: number | null
  onDelete: () => void
  onChange: (updated: Partial<CreateStepDto>) => void
}) {
  const cfg = STEP_TYPES[step.action]
  const Icon = cfg.icon
  const [previewText, setPreviewText] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const handleGeneratePreview = async () => {
    if (!campaignId) return
    setPreviewLoading(true)
    try {
      const msg = await campaignsService.previewMessage(campaignId, step.channel, step.action)
      setPreviewText(msg)
    } catch {
      setPreviewText('No se pudo generar la vista previa.')
    } finally {
      setPreviewLoading(false)
    }
  }

  return (
    <div className="flex gap-3 items-start">
      <div className="flex flex-col items-center pt-3 shrink-0">
        <span
          className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold border"
          style={{ background: cfg.bg, color: cfg.color, borderColor: cfg.border }}
        >
          {index + 1}
        </span>
        <div className="w-px flex-1 min-h-[16px] mt-1" style={{ background: BORDER }} />
      </div>

      <div
        className="flex-1 rounded-xl border bg-white overflow-hidden mb-2"
        style={{ borderColor: BORDER2, borderLeftWidth: 3, borderLeftColor: cfg.color }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b" style={{ borderColor: BORDER }}>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md flex items-center justify-center" style={{ background: cfg.bg }}>
              <Icon className="w-3 h-3" style={{ color: cfg.color }} />
            </div>
            <select
              value={step.action}
              onChange={e => onChange({ action: e.target.value as StepAction })}
              className="text-xs font-semibold bg-transparent border-none outline-none cursor-pointer"
              style={{ color: TEXT }}
            >
              {Object.entries(STEP_TYPES).map(([v, { label }]) => (
                <option key={v} value={v}>{label}</option>
              ))}
            </select>
          </div>
          <button
            onClick={onDelete}
            className="w-6 h-6 rounded-md flex items-center justify-center transition-colors hover:bg-red-50 hover:text-red-500"
            style={{ color: PLACEHOLDER }}
          >
            <X className="w-3 h-3" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 space-y-3">
          {step.action === 'send_message' && (
            <div className="space-y-2">
              <label className="flex items-center gap-2 text-[11px] cursor-pointer select-none" style={{ color: MUTED }}>
                <input
                  type="checkbox"
                  checked={step.use_ai_message ?? false}
                  onChange={e => { onChange({ use_ai_message: e.target.checked }); setPreviewText(null) }}
                  className="w-3.5 h-3.5 rounded accent-blue-600"
                />
                <Sparkles className="w-3 h-3" style={{ color: BLUE }} />
                Dejar que la IA genere el mensaje
              </label>

              {step.use_ai_message ? (
                <div className="space-y-2">
                  <div
                    className="rounded-xl border p-3 space-y-1.5"
                    style={{ borderColor: BLUE_BORDER, background: BLUE_LIGHT }}
                  >
                    {previewLoading ? (
                      <div className="flex items-center gap-2 text-[11px]" style={{ color: MUTED }}>
                        <Loader2 className="w-3 h-3 animate-spin" style={{ color: BLUE }} />
                        Generando vista previa…
                      </div>
                    ) : previewText ? (
                      <p className="text-xs leading-relaxed whitespace-pre-wrap" style={{ color: '#1E3A8A' }}>{previewText}</p>
                    ) : (
                      <p className="text-[11px] italic" style={{ color: MUTED }}>
                        La IA generará un mensaje personalizado para cada lead.
                      </p>
                    )}
                  </div>
                  {campaignId && (
                    <button
                      type="button"
                      onClick={handleGeneratePreview}
                      disabled={previewLoading}
                      className="flex items-center gap-1.5 text-[11px] font-medium transition-colors disabled:opacity-50 hover:underline"
                      style={{ color: previewText ? MUTED : BLUE }}
                    >
                      {previewText
                        ? <><RefreshCw className="w-3 h-3" /> Regenerar muestra</>
                        : <><Sparkles className="w-3 h-3" /> Ver muestra de mensaje</>}
                    </button>
                  )}
                </div>
              ) : (
                <textarea
                  value={step.message_text ?? ''}
                  onChange={e => onChange({ message_text: e.target.value })}
                  placeholder="Escribe el mensaje que se enviará al lead…"
                  rows={3}
                  className="w-full text-xs border rounded-xl px-3 py-2 resize-none outline-none transition-colors"
                  style={{
                    background: BG, borderColor: BORDER2,
                    color: TEXT, placeholder: PLACEHOLDER,
                  }}
                  onFocus={e => e.target.style.borderColor = BLUE}
                  onBlur={e => e.target.style.borderColor = BORDER2}
                />
              )}
            </div>
          )}

          {step.action === 'update_stage' && (
            <div className="flex items-center gap-2">
              <span className="text-[11px] w-14 shrink-0" style={{ color: MUTED }}>Etapa</span>
              <select
                value={step.target_stage ?? ''}
                onChange={e => onChange({ target_stage: e.target.value || undefined })}
                className="flex-1 bg-white text-xs border rounded-lg px-2 py-1.5 outline-none focus:border-[#1A56DB] transition-colors"
                style={{ borderColor: BORDER2, color: TEXT }}
              >
                <option value="">Seleccionar etapa…</option>
                {STAGES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          )}

          <div className="flex items-center gap-2 pt-1 border-t" style={{ borderColor: BORDER }}>
            <Clock className="w-3 h-3 shrink-0" style={{ color: PLACEHOLDER }} />
            <span className="text-[11px]" style={{ color: MUTED }}>Esperar</span>
            <input
              type="number" min={0}
              value={step.delay_hours}
              onChange={e => onChange({ delay_hours: Math.max(0, parseInt(e.target.value) || 0) })}
              className="w-14 bg-white text-xs border rounded-lg px-2 py-1 outline-none text-center focus:border-[#1A56DB] transition-colors"
              style={{ borderColor: BORDER2, color: TEXT }}
            />
            <span className="text-[11px]" style={{ color: MUTED }}>horas antes de este paso</span>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── CampaignOverviewPanel ─────────────────────────────────────────────────────
function CampaignOverviewPanel({ campaign }: { campaign: Campaign }) {
  const [stats, setStats] = useState<{ unique_leads: number; sent: number; pending: number; failed: number; total_steps: number; success_rate: number } | null>(null)
  const [matching, setMatching] = useState<{ total: number; note: string; leads: { id: number; name: string }[] } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const [s, m] = await Promise.all([
          campaignsService.getStats(campaign.id).catch(() => null),
          campaignsService.getMatchingLeads(campaign.id).catch(() => null),
        ])
        if (!cancelled) { setStats(s as typeof stats); setMatching(m as typeof matching) }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [campaign.id])

  const triggerLabel: Record<string, string> = {
    manual: 'Manual — aplícala a leads específicos',
    inactivity: `Automática — leads sin contacto`,
    lead_score: 'Automática — por puntuación de lead',
    stage_change: 'Automática — al cambiar de etapa',
  }

  const statusInfo = {
    draft:          { label: 'Borrador', desc: 'Configura los pasos y envía a revisión para activar.', icon: '✏️' },
    pending_review: { label: 'Esperando aprobación', desc: 'Un administrador debe revisar y activar esta campaña.', icon: '⏳' },
    active:         { label: 'Activa y ejecutándose', desc: 'La campaña se ejecuta automáticamente según el disparador.', icon: '🟢' },
    paused:         { label: 'Pausada', desc: 'La campaña no se ejecuta. Actívala para reanudar.', icon: '⏸️' },
    completed:      { label: 'Completada', desc: 'Esta campaña finalizó su ciclo de ejecución.', icon: '✅' },
  }[campaign.status] ?? { label: campaign.status, desc: '', icon: '•' }

  const sent = stats?.sent ?? 0
  const total = stats?.total_steps ?? 0
  const progress = total > 0 ? Math.round((sent / total) * 100) : 0

  return (
    <div className="rounded-xl border bg-white overflow-hidden" style={{ borderColor: BORDER2 }}>
      {/* Status row */}
      <div
        className="flex items-center gap-3 px-4 py-3 border-b"
        style={{
          borderColor: BORDER,
          background: campaign.status === 'active' ? '#F0FDF4' : campaign.status === 'paused' ? '#FFF7ED' : campaign.status === 'pending_review' ? '#FFFBEB' : '#F8FAFC',
        }}
      >
        <span className="text-base">{statusInfo.icon}</span>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold" style={{ color: TEXT }}>{statusInfo.label}</p>
          <p className="text-[11px]" style={{ color: MUTED }}>{statusInfo.desc}</p>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-[10px] font-medium uppercase tracking-wider" style={{ color: MUTED }}>Disparador</p>
          <p className="text-[11px] font-semibold" style={{ color: TEXT2 }}>
            {triggerLabel[campaign.triggered_by] ?? campaign.triggered_by}
          </p>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 divide-x" style={{ borderColor: BORDER }}>
        {[
          { label: 'Leads afectados', value: loading ? '…' : String(stats?.unique_leads ?? 0), icon: Users, color: BLUE },
          { label: 'Enviados', value: loading ? '…' : String(sent), icon: TrendingUp, color: '#059669' },
          { label: 'Pendientes', value: loading ? '…' : String(stats?.pending ?? 0), icon: Activity, color: '#D97706' },
          { label: 'Tasa de éxito', value: loading ? '…' : `${stats?.success_rate?.toFixed(0) ?? 0}%`, icon: Target, color: '#7C3AED' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="flex flex-col items-center gap-1 py-3 px-2">
            <Icon className="w-3.5 h-3.5" style={{ color }} />
            <span className="text-[18px] font-bold tabular-nums" style={{ color: TEXT }}>{value}</span>
            <span className="text-[10px] text-center" style={{ color: MUTED }}>{label}</span>
          </div>
        ))}
      </div>

      {/* Progress bar (only if there's activity) */}
      {total > 0 && (
        <div className="px-4 py-3 border-t space-y-1.5" style={{ borderColor: BORDER }}>
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium" style={{ color: MUTED }}>Progreso de ejecución</span>
            <span className="text-[11px] font-semibold" style={{ color: TEXT }}>{sent} / {total} pasos enviados</span>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: '#E5E7EB' }}>
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${progress}%`, background: progress === 100 ? '#059669' : BLUE }}
            />
          </div>
        </div>
      )}

      {/* Matching leads */}
      {matching && (
        <div className="px-4 py-3 border-t space-y-2" style={{ borderColor: BORDER }}>
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-semibold" style={{ color: TEXT }}>
              Leads que coinciden ahora
            </p>
            <span
              className="px-2 py-0.5 rounded-full text-[10px] font-bold border"
              style={{ background: BLUE_LIGHT, color: BLUE, borderColor: BLUE_BORDER }}
            >
              {matching.total}
            </span>
          </div>
          <p className="text-[11px]" style={{ color: MUTED }}>{matching.note}</p>
          {matching.leads.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-1">
              {matching.leads.slice(0, 5).map(l => (
                <span
                  key={l.id}
                  className="px-2 py-0.5 rounded-lg border text-[10px] font-medium"
                  style={{ background: '#F8FAFC', borderColor: BORDER2, color: TEXT2 }}
                >
                  {l.name}
                </span>
              ))}
              {matching.total > 5 && (
                <span className="text-[10px]" style={{ color: MUTED }}>+{matching.total - 5} más</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── EmptyEditor ───────────────────────────────────────────────────────────────
function EmptyEditor() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 p-10">
      <div
        className="w-16 h-16 rounded-2xl flex items-center justify-center border"
        style={{ background: BLUE_LIGHT, borderColor: BLUE_BORDER }}
      >
        <Megaphone className="w-7 h-7" style={{ color: BLUE }} />
      </div>
      <div className="text-center space-y-1">
        <p className="text-sm font-semibold" style={{ color: TEXT }}>Selecciona una campaña</p>
        <p className="text-xs" style={{ color: MUTED }}>Elige una de la lista o crea una nueva para configurar su flujo.</p>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export function CampaignsPage() {
  const { isAdmin } = usePermissions()

  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [listLoading, setListLoading] = useState(true)
  const [selected, setSelected] = useState<Campaign | null>(null)

  const [editName, setEditName] = useState('')
  const [editDesc, setEditDesc] = useState('')
  const [editChannel, setEditChannel] = useState<CampaignChannel>('whatsapp')
  const [editTrigger, setEditTrigger] = useState<CampaignTrigger>('manual')
  const [editCondition, setEditCondition] = useState<Record<string, unknown>>({})
  const [localSteps, setLocalSteps] = useState<(CreateStepDto & { _localId: string })[]>([])

  const [saving, setSaving] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newChannel, setNewChannel] = useState<CampaignChannel>('whatsapp')
  const [creating, setCreating] = useState(false)

  const [applyLeadId, setApplyLeadId] = useState('')
  const [applying, setApplying] = useState(false)

  const loadCampaigns = useCallback(async () => {
    setListLoading(true)
    try {
      const data = await campaignsService.getAll()
      setCampaigns(Array.isArray(data) ? data : [])
    } catch (e) { toast.error(getErrorMessage(e)) }
    finally { setListLoading(false) }
  }, [])

  useEffect(() => { loadCampaigns() }, [loadCampaigns])

  const selectCampaign = useCallback((c: Campaign) => {
    setSelected(c); setEditName(c.name); setEditDesc(c.description ?? '')
    setEditChannel(c.channel); setEditTrigger(c.triggered_by)
    setEditCondition(c.trigger_condition ?? {}); setLocalSteps([])
  }, [])

  const handleSave = async () => {
    if (!selected) return
    setSaving(true)
    try {
      const updated = await campaignsService.update(selected.id, {
        name: editName, description: editDesc || undefined,
        channel: editChannel, triggered_by: editTrigger, trigger_condition: editCondition,
      })
      for (const s of localSteps) {
        const { _localId, ...dto } = s
        await campaignsService.addStep(selected.id, dto)
      }
      const fresh = await campaignsService.getOne(selected.id)
      setCampaigns(prev => prev.map(c => c.id === fresh.id ? fresh : c))
      setSelected(fresh); setLocalSteps([])
      toast.success('Campaña guardada')
    } catch (e) { toast.error(getErrorMessage(e)) }
    finally { setSaving(false) }
  }

  const handleDeleteStep = async (stepId: number) => {
    if (!selected) return
    try {
      await campaignsService.deleteStep(selected.id, stepId)
      const fresh = await campaignsService.getOne(selected.id)
      setCampaigns(prev => prev.map(c => c.id === fresh.id ? fresh : c))
      setSelected(fresh); toast.success('Paso eliminado')
    } catch (e) { toast.error(getErrorMessage(e)) }
  }

  const addLocalStep = () => {
    const nextNum = (selected?.steps?.length ?? 0) + localSteps.length + 1
    setLocalSteps(prev => [...prev, {
      _localId: `local_${Date.now()}`, step_number: nextNum,
      action: 'send_message', delay_hours: 0, use_ai_message: false,
    }])
  }

  const handleStatusAction = async (action: 'submit' | 'activate' | 'pause') => {
    if (!selected) return
    setActionLoading(action)
    try {
      const fn = {
        submit:   () => campaignsService.submitForReview(selected.id),
        activate: () => campaignsService.activate(selected.id),
        pause:    () => campaignsService.pause(selected.id),
      }[action]
      const updated = await fn()
      setCampaigns(prev => prev.map(c => c.id === updated.id ? updated : c))
      setSelected(updated)
      toast.success({ submit: 'Enviada a revisión', activate: 'Campaña activada', pause: 'Campaña pausada' }[action])
    } catch (e) { toast.error(getErrorMessage(e)) }
    finally { setActionLoading(null) }
  }

  const handleDelete = async (c: Campaign, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(`¿Eliminar "${c.name}"?`)) return
    try {
      await campaignsService.delete(c.id)
      setCampaigns(prev => prev.filter(x => x.id !== c.id))
      if (selected?.id === c.id) setSelected(null)
      toast.success('Campaña eliminada')
    } catch (e) { toast.error(getErrorMessage(e)) }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newName.trim()) return
    setCreating(true)
    try {
      const c = await campaignsService.create({ name: newName.trim(), channel: newChannel })
      setCampaigns(prev => [c, ...prev])
      selectCampaign(c); setShowCreate(false); setNewName('')
      toast.success('Campaña creada')
    } catch (e) { toast.error(getErrorMessage(e)) }
    finally { setCreating(false) }
  }

  const handleApply = async () => {
    if (!selected || !applyLeadId.trim()) return
    setApplying(true)
    try {
      await campaignsService.applyToLead(selected.id, parseInt(applyLeadId))
      toast.success('Campaña aplicada al lead'); setApplyLeadId('')
    } catch (e) { toast.error(getErrorMessage(e)) }
    finally { setApplying(false) }
  }

  const savedSteps = selected?.steps ?? []

  return (
    <div className="h-full flex flex-col" style={{ background: BG }}>

      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <div
        className="px-7 py-4 flex items-center justify-between shrink-0 border-b bg-white"
        style={{ borderColor: BORDER }}
      >
        <div>
          <h1 className="text-[17px] font-bold" style={{ color: TEXT }}>Campañas</h1>
          <p className="text-[12px] mt-0.5" style={{ color: MUTED }}>
            {campaigns.length > 0 ? `${campaigns.length} campaña${campaigns.length !== 1 ? 's' : ''}` : 'Automatizaciones de seguimiento'}
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-colors hover:opacity-90"
          style={{ background: BLUE }}
        >
          <Plus className="w-4 h-4" />
          Nueva campaña
        </button>
      </div>

      {/* ── Body ────────────────────────────────────────────────────────── */}
      <div className="flex-1 flex overflow-hidden">

        {/* Left: campaign list */}
        <div
          className="w-72 shrink-0 flex flex-col border-r bg-white overflow-y-auto"
          style={{ borderColor: BORDER }}
        >
          {listLoading ? (
            <div className="flex-1 flex items-center justify-center">
              <LoadingSpinner size="sm" />
            </div>
          ) : campaigns.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 px-6 py-10 text-center">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center border" style={{ background: BLUE_LIGHT, borderColor: BLUE_BORDER }}>
                <Megaphone className="w-5 h-5" style={{ color: BLUE }} />
              </div>
              <div>
                <p className="text-sm font-medium" style={{ color: TEXT }}>Sin campañas</p>
                <p className="text-xs mt-1" style={{ color: MUTED }}>Crea tu primera campaña de seguimiento</p>
              </div>
            </div>
          ) : (
            <ul className="py-2">
              {campaigns.map(c => {
                const isSelected = selected?.id === c.id
                return (
                  <li key={c.id} className="group">
                    <button
                      onClick={() => selectCampaign(c)}
                      className={`w-full text-left px-4 py-3 flex items-start gap-3 transition-all border-r-2 ${
                        isSelected
                          ? 'bg-[#EBF2FF] border-r-[#1A56DB]'
                          : 'hover:bg-[#F8FAFC] border-r-transparent'
                      }`}
                    >
                      {/* Status dot */}
                      <div className="mt-1 shrink-0">
                        <span
                          className="block w-2 h-2 rounded-full"
                          style={{ background: STATUS_CONFIG[c.status]?.dot ?? '#9CA3AF' }}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-semibold truncate" style={{ color: isSelected ? BLUE : TEXT }}>
                          {c.name}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded-full font-medium border"
                            style={{
                              background: STATUS_CONFIG[c.status]?.bg ?? '#F3F4F6',
                              color: STATUS_CONFIG[c.status]?.text ?? '#374151',
                              borderColor: STATUS_CONFIG[c.status]?.border ?? '#D1D5DB',
                            }}
                          >
                            {STATUS_CONFIG[c.status]?.label ?? c.status}
                          </span>
                          <span className="text-[10px]" style={{ color: PLACEHOLDER }}>
                            {c.steps?.length ?? 0} paso{(c.steps?.length ?? 0) !== 1 ? 's' : ''}
                          </span>
                        </div>
                      </div>
                      <button
                        onClick={e => handleDelete(c, e)}
                        className="shrink-0 w-6 h-6 rounded-md flex items-center justify-center transition-colors opacity-0 group-hover:opacity-100 hover:bg-red-50 hover:text-red-500"
                        style={{ color: PLACEHOLDER }}
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* Right: editor */}
        {!selected ? (
          <EmptyEditor />
        ) : (
          <div className="flex-1 flex flex-col overflow-hidden">

            {/* Editor top bar */}
            <div className="px-6 py-3.5 border-b bg-white flex items-center justify-between shrink-0" style={{ borderColor: BORDER }}>
              <div className="flex items-center gap-3">
                <StatusBadge status={selected.status} />
                <input
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  className="text-[15px] font-bold bg-transparent border-b-2 border-transparent hover:border-[#E2EAF4] focus:border-[#1A56DB] outline-none transition-colors py-0.5 min-w-0"
                  style={{ color: TEXT }}
                />
              </div>
              <div className="flex items-center gap-2">
                {selected.status === 'draft' && (
                  <button
                    onClick={() => handleStatusAction('submit')}
                    disabled={!!actionLoading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors disabled:opacity-50 hover:bg-amber-50"
                    style={{ color: '#92400E', borderColor: '#FCD34D', background: '#FEF3C7' }}
                  >
                    {actionLoading === 'submit' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                    Enviar a revisión
                  </button>
                )}
                {selected.status === 'pending_review' && isAdmin && (
                  <button
                    onClick={() => handleStatusAction('activate')}
                    disabled={!!actionLoading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors disabled:opacity-50 hover:bg-green-50"
                    style={{ color: '#065F46', borderColor: '#6EE7B7', background: '#D1FAE5' }}
                  >
                    {actionLoading === 'activate' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                    Activar campaña
                  </button>
                )}
                {selected.status === 'active' && isAdmin && (
                  <button
                    onClick={() => handleStatusAction('pause')}
                    disabled={!!actionLoading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors disabled:opacity-50 hover:bg-orange-50"
                    style={{ color: '#7C2D12', borderColor: '#FDBA74', background: '#FFEDD5' }}
                  >
                    {actionLoading === 'pause' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Pause className="w-3.5 h-3.5" />}
                    Pausar
                  </button>
                )}
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold text-white disabled:opacity-50 transition-colors hover:opacity-90"
                  style={{ background: BLUE }}
                >
                  {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5" />}
                  Guardar
                </button>
              </div>
            </div>

            {/* Scrollable editor body */}
            <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6" style={{ background: BG }}>

              {/* Overview stats panel */}
              <CampaignOverviewPanel campaign={selected} />

              {/* Descripción + Canal (side by side) */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: MUTED }}>Descripción</label>
                  <input
                    value={editDesc}
                    onChange={e => setEditDesc(e.target.value)}
                    placeholder="Describe el objetivo…"
                    className="w-full text-sm border rounded-xl px-3 py-2.5 outline-none transition-colors bg-white"
                    style={{ borderColor: BORDER2, color: TEXT }}
                    onFocus={e => e.target.style.borderColor = BLUE}
                    onBlur={e => e.target.style.borderColor = BORDER2}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: MUTED }}>Canal principal</label>
                  <div className="flex gap-1.5 flex-wrap">
                    {CHANNELS.map(c => (
                      <button
                        key={c.value}
                        onClick={() => setEditChannel(c.value)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                          editChannel === c.value
                            ? 'border-[#BFCFFF] bg-[#EBF2FF] text-[#1A56DB]'
                            : 'border-[#E2EAF4] bg-white text-[#6B7280] hover:border-[#BFCFFF] hover:text-[#1A56DB]'
                        }`}
                      >
                        {c.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Trigger */}
              <div className="space-y-2">
                <label className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: MUTED }}>Disparador</label>
                <TriggerConfig
                  trigger={editTrigger}
                  condition={editCondition}
                  onChange={(t, c) => { setEditTrigger(t); setEditCondition(c) }}
                />
              </div>

              {/* Flow builder */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: MUTED }}>
                    Flujo · {savedSteps.length + localSteps.length} paso{(savedSteps.length + localSteps.length) !== 1 ? 's' : ''}
                  </label>
                </div>

                <div className="space-y-0">
                  {/* Saved steps */}
                  {savedSteps.map((step, i) => (
                    <SavedStepRow
                      key={step.id}
                      step={step}
                      index={i}
                      onDelete={() => handleDeleteStep(step.id)}
                      onSaved={updated => {
                        setSelected(prev => {
                          if (!prev) return prev
                          const newSteps = (prev.steps ?? []).map(s => s.id === updated.id ? updated : s)
                          const next = { ...prev, steps: newSteps }
                          setCampaigns(cs => cs.map(c => c.id === next.id ? next : c))
                          return next
                        })
                      }}
                    />
                  ))}

                  {/* Local steps */}
                  {localSteps.map((step, i) => (
                    <StepCard
                      key={step._localId}
                      step={step}
                      index={savedSteps.length + i}
                      campaignId={selected?.id ?? null}
                      onDelete={() => setLocalSteps(prev => prev.filter(s => s._localId !== step._localId))}
                      onChange={updated =>
                        setLocalSteps(prev => prev.map(s =>
                          s._localId === step._localId ? { ...s, ...updated } : s
                        ))
                      }
                    />
                  ))}

                  {/* Add step */}
                  <div className="flex justify-center pt-3">
                    <button
                      onClick={addLocalStep}
                      className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold border-2 border-dashed transition-all hover:border-[#1A56DB] hover:text-[#1A56DB] hover:bg-[#EBF2FF]"
                      style={{ borderColor: BORDER2, color: MUTED }}
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Agregar paso
                    </button>
                  </div>
                </div>
              </div>

              {/* Apply to lead */}
              {selected.status === 'active' && (
                <div
                  className="rounded-xl border bg-white p-4 space-y-3"
                  style={{ borderColor: BORDER2 }}
                >
                  <label className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: MUTED }}>Aplicar a lead</label>
                  <div className="flex gap-2">
                    <input
                      type="number"
                      value={applyLeadId}
                      onChange={e => setApplyLeadId(e.target.value)}
                      placeholder="ID del lead"
                      className="flex-1 text-sm border rounded-xl px-3 py-2 outline-none transition-colors bg-white"
                      style={{ borderColor: BORDER2, color: TEXT }}
                      onFocus={e => e.target.style.borderColor = BLUE}
                      onBlur={e => e.target.style.borderColor = BORDER2}
                    />
                    <button
                      onClick={handleApply}
                      disabled={applying || !applyLeadId}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold text-white disabled:opacity-50 transition-colors hover:opacity-90"
                      style={{ background: BLUE }}
                    >
                      {applying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Users className="w-4 h-4" />}
                      Aplicar
                    </button>
                  </div>
                </div>
              )}

              {/* Pending review notice */}
              {selected.status === 'pending_review' && !isAdmin && (
                <div
                  className="rounded-xl border p-4 flex items-start gap-3"
                  style={{ borderColor: '#FCD34D', background: '#FFFBEB' }}
                >
                  <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" style={{ color: '#D97706' }} />
                  <p className="text-xs" style={{ color: '#92400E' }}>
                    Esta campaña está pendiente de revisión. Un administrador debe aprobarla antes de activarse.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Create dialog ────────────────────────────────────────────────── */}
      {showCreate && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
          onClick={() => setShowCreate(false)}
        >
          <div
            className="w-[420px] rounded-2xl border bg-white p-6 shadow-xl space-y-5"
            style={{ borderColor: BORDER }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold" style={{ color: TEXT }}>Nueva campaña</h2>
                <p className="text-xs mt-0.5" style={{ color: MUTED }}>Configura los detalles básicos para empezar</p>
              </div>
              <button
                onClick={() => setShowCreate(false)}
                className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors hover:bg-[#F3F4F6]"
                style={{ color: MUTED }}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium" style={{ color: MUTED }}>Nombre</label>
                <input
                  autoFocus
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  placeholder="Ej: Seguimiento leads inactivos"
                  className="w-full text-sm border rounded-xl px-4 py-2.5 outline-none transition-colors bg-white"
                  style={{ borderColor: BORDER2, color: TEXT }}
                  onFocus={e => e.target.style.borderColor = BLUE}
                  onBlur={e => e.target.style.borderColor = BORDER2}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium" style={{ color: MUTED }}>Canal principal</label>
                <div className="flex gap-2 flex-wrap">
                  {CHANNELS.map(c => (
                    <button
                      key={c.value}
                      type="button"
                      onClick={() => setNewChannel(c.value)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                        newChannel === c.value
                          ? 'border-[#BFCFFF] bg-[#EBF2FF] text-[#1A56DB]'
                          : 'border-[#E2EAF4] text-[#6B7280] hover:border-[#BFCFFF] hover:text-[#1A56DB]'
                      }`}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="flex-1 py-2.5 rounded-xl text-sm font-medium border transition-colors hover:bg-[#F8FAFC]"
                  style={{ borderColor: BORDER2, color: MUTED }}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={creating || !newName.trim()}
                  className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50 transition-colors hover:opacity-90"
                  style={{ background: BLUE }}
                >
                  {creating ? <Loader2 className="w-4 h-4 animate-spin mx-auto" /> : 'Crear campaña'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
