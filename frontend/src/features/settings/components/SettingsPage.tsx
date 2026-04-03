import { useState, useEffect, useRef } from 'react'
import {
  Save, Loader2, TrendingUp, Database, ListOrdered,
  AlertTriangle, GripVertical, ChevronRight, Bot, Calendar,
  Plus, Trash2, Clock,
} from 'lucide-react'
import { CalendarSection } from './CalendarSection'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/shared/components/ui/dialog'
import {
  DndContext, closestCenter, KeyboardSensor, PointerSensor,
  useSensor, useSensors, type DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove, SortableContext, sortableKeyboardCoordinates,
  useSortable, verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { toast } from 'sonner'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import { Badge } from '@/shared/components/ui/badge'
import { Textarea } from '@/shared/components/ui/textarea'
import { LoadingSpinner } from '@/shared/components/common/LoadingSpinner'
import { getErrorMessage } from '@/shared/types/api'
import { useAuthStore } from '@/features/auth/store/authStore'
import { settingsService, type QualificationConfig, type ScoringConfig, type IncomeTier, type AgentPromptsConfig, type AvailabilitySlot, type AppointmentBlock, DEFAULT_SCORING_CONFIG } from '../services/settings.service'

// ── Design tokens ─────────────────────────────────────────────────────────────
const blue   = '#1A56DB'
const blueLt = '#EBF2FF'
const border = '#D1D9E6'
const bg     = '#F0F4F8'

// ── Helpers ───────────────────────────────────────────────────────────────────
const fmtClp = (v: number) =>
  new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(v)

interface ClpInputProps { value: number; onChange: (v: number) => void; placeholder?: string }
function ClpInput({ value, onChange, placeholder }: ClpInputProps) {
  const [display, setDisplay] = useState(value > 0 ? value.toLocaleString('es-CL') : '')
  useEffect(() => { setDisplay(value > 0 ? value.toLocaleString('es-CL') : '') }, [value])
  return (
    <div className="relative">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm font-bold" style={{ color: blue }}>$</span>
      <Input
        className="pl-7"
        style={{ '--ring': blue } as React.CSSProperties}
        value={display}
        placeholder={placeholder}
        onChange={(e) => {
          const d = e.target.value.replace(/\D/g, '')
          const n = d ? parseInt(d, 10) : 0
          setDisplay(n > 0 ? n.toLocaleString('es-CL') : '')
          onChange(n)
        }}
        onBlur={() => setDisplay(value > 0 ? value.toLocaleString('es-CL') : '')}
      />
    </div>
  )
}

// ── Score bar ─────────────────────────────────────────────────────────────────
function ScoreBar({ cold, warm, qualified }: { cold: number; warm: number; qualified: number }) {
  const segments = [
    { label: 'Frío',       width: cold,            from: '#BFDBFE', to: '#93C5FD', textColor: '#1E40AF' },
    { label: 'Tibio',      width: warm - cold,     from: '#60A5FA', to: '#3B82F6', textColor: '#fff' },
    { label: 'Caliente',   width: qualified - warm, from: '#2563EB', to: '#1D4ED8', textColor: '#fff' },
    { label: 'Calificado', width: 100 - qualified, from: '#1A56DB', to: '#1648C0', textColor: '#fff' },
  ]
  return (
    <div className="space-y-2">
      <div className="flex h-7 rounded-xl overflow-hidden shadow-inner text-[11px] font-semibold">
        {segments.map((s) => (
          <div
            key={s.label}
            className="flex items-center justify-center transition-all duration-300"
            style={{
              width: `${Math.max(s.width, 0)}%`,
              background: `linear-gradient(90deg, ${s.from}, ${s.to})`,
              color: s.textColor,
            }}
          >
            {s.width >= 12 ? s.label : ''}
          </div>
        ))}
      </div>
      <div className="flex justify-between text-xs px-0.5" style={{ color: '#9CA3AF' }}>
        <span>0</span><span>{cold}</span><span>{warm}</span><span>{qualified}</span><span>100</span>
      </div>
    </div>
  )
}

// ── Sortable field item ───────────────────────────────────────────────────────
const FIELD_META: Record<string, { label: string; hint: string; emoji: string }> = {
  name:           { label: 'Nombre completo',      hint: 'Identidad básica',              emoji: '👤' },
  phone:          { label: 'Teléfono',             hint: 'Canal principal de contacto',   emoji: '📱' },
  email:          { label: 'Email',                hint: 'Seguimiento digital',            emoji: '✉️' },
  location:       { label: 'Ubicación / comuna',   hint: 'Filtra propiedades relevantes', emoji: '📍' },
  monthly_income: { label: 'Renta mensual',        hint: 'Clave para calificar',          emoji: '💵' },
  dicom_status:   { label: 'Estado DICOM',         hint: 'Determina elegibilidad',        emoji: '🏦' },
  budget:         { label: 'Presupuesto',          hint: 'Intención de compra',           emoji: '💰' },
}

function SortableField({ id, index }: { id: string; index: number }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id })
  const meta = FIELD_META[id] ?? { label: id, hint: '', emoji: '•' }
  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        boxShadow: isDragging ? '0 8px 24px rgba(26,86,219,0.18)' : undefined,
        borderColor: isDragging ? blue : border,
        zIndex: isDragging ? 50 : undefined,
      }}
      className="group flex items-center gap-3 rounded-xl border bg-white px-4 py-3 select-none"
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing touch-none shrink-0 opacity-40 group-hover:opacity-80 transition-opacity"
        style={{ color: blue }}
      >
        <GripVertical className="h-4 w-4" />
      </button>
      <span
        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
        style={{ background: blueLt, color: blue }}
      >
        {index + 1}
      </span>
      <span className="text-base">{meta.emoji}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-[#111827] leading-tight">{meta.label}</p>
        <p className="text-xs text-[#9CA3AF] leading-tight">{meta.hint}</p>
      </div>
      <ChevronRight className="h-3.5 w-3.5 text-[#D1D9E6] shrink-0" />
    </div>
  )
}

// ── Tab definitions ───────────────────────────────────────────────────────────
const TABS = [
  { id: 'scoring',  label: 'Calificación', icon: TrendingUp  },
  { id: 'weights',  label: 'Scoring',       icon: Database    },
  { id: 'agent',    label: 'Agente IA',    icon: ListOrdered },
  { id: 'prompt',   label: 'Prompt',        icon: Bot         },
  { id: 'calendar', label: 'Calendario',       icon: Calendar  },
] as const
type TabId = (typeof TABS)[number]['id']

// ── Main page ─────────────────────────────────────────────────────────────────
export function SettingsPage() {
  const [cfg, setCfg]         = useState<QualificationConfig | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving]   = useState(false)
  const [activeTab, setActiveTab] = useState<TabId>('scoring')
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0 })
  const [agentPrompts, setAgentPrompts] = useState<AgentPromptsConfig | null>(null)
  const [agentCustom, setAgentCustom] = useState({ qualifier: '', scheduler: '', follow_up: '' })

  // Availability
  const [slots, setSlots] = useState<AvailabilitySlot[]>([])
  const [blocks, setBlocks] = useState<AppointmentBlock[]>([])
  const [slotsLoading, setSlotsLoading] = useState(false)
  // Slot dialog
  const [slotDialog, setSlotDialog] = useState<{ open: boolean; editing: AvailabilitySlot | null; day: number }>({ open: false, editing: null, day: 0 })
  const [slotForm, setSlotForm] = useState({ day_of_week: 0, start_time: '09:00', end_time: '18:00', slot_duration_minutes: 60 })
  const [slotSaving, setSlotSaving] = useState(false)
  // Block dialog
  const [blockDialog, setBlockDialog] = useState(false)
  const [blockForm, setBlockForm] = useState({ start_time: '', end_time: '', reason: '' })
  const [blockSaving, setBlockSaving] = useState(false)
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const isAdmin = useAuthStore((s) => s.isAdmin())

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  useEffect(() => {
    settingsService.getConfig()
      .then(setCfg)
      .catch((e) => toast.error(getErrorMessage(e)))
      .finally(() => setIsLoading(false))
  }, [])

  // Load availability slots when switching to calendar tab
  useEffect(() => {
    if (activeTab !== 'calendar') return
    setSlotsLoading(true)
    Promise.all([
      settingsService.getAvailabilitySlots(),
      settingsService.getBlocks(),
    ])
      .then(([s, b]) => { setSlots(s); setBlocks(b) })
      .catch(() => { /* non-critical */ })
      .finally(() => setSlotsLoading(false))
  }, [activeTab])

  // When switching to prompt tab, load agent prompts
  useEffect(() => {
    if (activeTab !== 'prompt' || !isAdmin) return

    settingsService.getAgentPrompts()
      .then((data) => {
        setAgentPrompts(data)
        setAgentCustom({
          qualifier: data.qualifier.custom,
          scheduler: data.scheduler.custom,
          follow_up: data.follow_up.custom,
        })
      })
      .catch(() => { /* non-critical */ })
  }, [activeTab, isAdmin])

  // Animate tab indicator
  useEffect(() => {
    const el = tabRefs.current[activeTab]
    if (!el) return
    const parent = el.parentElement!
    const parentRect = parent.getBoundingClientRect()
    const rect = el.getBoundingClientRect()
    setIndicatorStyle({ left: rect.left - parentRect.left, width: rect.width })
  }, [activeTab])

  const set = <K extends keyof QualificationConfig>(key: K, val: QualificationConfig[K]) =>
    setCfg((prev) => prev ? { ...prev, [key]: val } : prev)

  const setTier = (index: number, field: keyof IncomeTier, value: number | string) =>
    setCfg((prev) => {
      if (!prev) return prev
      const tiers = [...(prev.scoring_config?.income_tiers ?? DEFAULT_SCORING_CONFIG.income_tiers)]
      tiers[index] = { ...tiers[index], [field]: field === 'label' ? value : Number(value) }
      return { ...prev, scoring_config: { ...prev.scoring_config, income_tiers: tiers } }
    })

  const setScoringPts = (field: 'dicom_clean_pts' | 'dicom_has_debt_pts', value: number) =>
    setCfg((prev) => {
      if (!prev) return prev
      return { ...prev, scoring_config: { ...prev.scoring_config, [field]: value } }
    })

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id || !cfg) return
    const oldIndex = cfg.field_priority.indexOf(active.id as string)
    const newIndex = cfg.field_priority.indexOf(over.id as string)
    set('field_priority', arrayMove(cfg.field_priority, oldIndex, newIndex))
  }

  const handleSave = async () => {
    if (!cfg) return
    setIsSaving(true)
    try {
      await settingsService.saveConfig(cfg)
      if (activeTab === 'prompt') {
        await settingsService.saveAgentPrompts(agentCustom)
      }
      toast.success('Configuración guardada')
    } catch (e) {
      toast.error(getErrorMessage(e))
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <LoadingSpinner size="lg" />
      </div>
    )
  }
  if (!cfg) return null

  // ── Tab content ─────────────────────────────────────────────────────────────
  const tabContent: Record<TabId, React.ReactNode> = {

    // ── TAB 1: SCORING ────────────────────────────────────────────────────────
    scoring: (
      <div className="space-y-8">
        {/* Score thresholds */}
        <div>
          <SectionLabel>Umbrales de score</SectionLabel>
          <p className="text-sm text-[#6B7280] mb-5">
            Define cuántos puntos separan cada nivel. Los leads suben de nivel a medida que el agente recopila sus datos.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            {([
              { key: 'cold_max_score',      label: 'Frío',       color: '#BFDBFE', textColor: '#1E40AF', dot: '#60A5FA' },
              { key: 'warm_max_score',      label: 'Tibio',      color: '#FEF3C7', textColor: '#92400E', dot: '#F59E0B' },
              { key: 'hot_min_score',       label: 'Caliente',   color: '#FFEDD5', textColor: '#9A3412', dot: '#F97316' },
              { key: 'qualified_min_score', label: 'Calificado', color: '#DCFCE7', textColor: '#166534', dot: '#22C55E' },
            ] as const).map(({ key, label, color, textColor, dot }) => (
              <div key={key} className="rounded-xl border p-4 space-y-3" style={{ borderColor: border, background: '#fff' }}>
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: dot }} />
                  <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: textColor }}>{label}</span>
                </div>
                <div className="relative">
                  <Input
                    type="number" min={0} max={100}
                    value={cfg[key]}
                    onChange={(e) => set(key, Math.min(100, Math.max(0, parseInt(e.target.value) || 0)))}
                    className="text-center text-2xl font-bold h-14 pr-10"
                    style={{ color: textColor }}
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium text-[#9CA3AF]">pts</span>
                </div>
                <div className="h-1.5 rounded-full" style={{ background: color }}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${cfg[key]}%`, background: dot }} />
                </div>
              </div>
            ))}
          </div>
          <div className="rounded-xl border p-4" style={{ borderColor: border, background: '#fff' }}>
            <p className="text-xs font-semibold text-[#6B7280] uppercase tracking-widest mb-3">Vista previa del espectro</p>
            <ScoreBar cold={cfg.cold_max_score} warm={cfg.warm_max_score} qualified={cfg.qualified_min_score} />
          </div>
        </div>

        {/* Financial */}
        <div>
          <SectionLabel>Calificación financiera</SectionLabel>
          <p className="text-sm text-[#6B7280] mb-5">
            El agente usa estos umbrales para clasificar a los leads según su capacidad económica real.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {([
              { key: 'min_income_calificado', badge: 'CALIFICADO', badgeBg: '#DCFCE7', badgeText: '#166534', badgeBorder: '#BBF7D0', sub: 'DICOM limpio requerido' },
              { key: 'min_income_potencial',  badge: 'POTENCIAL',  badgeBg: '#FEF3C7', badgeText: '#92400E', badgeBorder: '#FDE68A', sub: 'Acepta DICOM con deuda' },
              { key: 'max_acceptable_debt',   badge: 'DEUDA MÁX',  badgeBg: '#FEE2E2', badgeText: '#991B1B', badgeBorder: '#FECACA', sub: 'Si supera → NO califica', icon: true },
            ] as const).map(({ key, badge, badgeBg, badgeText, badgeBorder, sub, icon }) => (
              <div key={key} className="rounded-xl border p-4 space-y-3" style={{ borderColor: border, background: '#fff' }}>
                <span
                  className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border"
                  style={{ background: badgeBg, color: badgeText, borderColor: badgeBorder }}
                >
                  {icon && <AlertTriangle className="h-2.5 w-2.5" />}
                  {badge}
                </span>
                <ClpInput
                  value={cfg[key as keyof QualificationConfig] as number}
                  onChange={(v) => set(key as keyof QualificationConfig, v as never)}
                  placeholder="0"
                />
                <p className="text-xs text-[#9CA3AF]">{sub}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Rules summary */}
        <div className="rounded-xl p-5 border" style={{ background: blueLt, borderColor: `${blue}30` }}>
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] mb-4" style={{ color: blue }}>Reglas activas</p>
          <div className="space-y-2.5">
            {[
              { dot: '#22C55E', text: <><strong>CALIFICADO</strong> — renta ≥ {fmtClp(cfg.min_income_calificado)}, DICOM limpio</> },
              { dot: '#F59E0B', text: <><strong>POTENCIAL</strong> — renta ≥ {fmtClp(cfg.min_income_potencial)}, deuda ≤ {fmtClp(cfg.max_acceptable_debt)}</> },
              { dot: '#EF4444', text: <><strong>NO CALIFICA</strong> — renta &lt; {fmtClp(cfg.min_income_potencial)} <em>o</em> deuda &gt; {fmtClp(cfg.max_acceptable_debt)}</> },
              { dot: '#7C3AED', text: <><strong>DICOM sucio</strong> — bloqueo automático de agendamiento</> },
            ].map((r, i) => (
              <div key={i} className="flex items-start gap-2.5 text-sm text-[#374151]">
                <span className="mt-1.5 h-2 w-2 rounded-full shrink-0" style={{ background: r.dot }} />
                <span>{r.text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Income tiers for scoring */}
        <div>
          <SectionLabel>Tramos de Sueldo — Puntuación</SectionLabel>
          <p className="text-sm text-[#6B7280] mb-5">
            Define cuántos puntos del score (0-40) aporta cada nivel de sueldo mensual.
            Un lead con sueldo alto suma más puntos aunque no tenga todos los datos del perfil.
          </p>
          <div className="rounded-xl border overflow-hidden" style={{ borderColor: border }}>
            {/* Header */}
            <div className="grid grid-cols-[1fr_180px_90px] gap-0 bg-[#F8FAFC] px-4 py-2.5 border-b" style={{ borderColor: border }}>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#6B7280]">Nivel</span>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#6B7280]">Sueldo mínimo</span>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#6B7280] text-right">Puntos</span>
            </div>
            {(cfg.scoring_config?.income_tiers ?? DEFAULT_SCORING_CONFIG.income_tiers).map((tier, i) => {
              const isLast = i === (cfg.scoring_config?.income_tiers ?? DEFAULT_SCORING_CONFIG.income_tiers).length - 1
              const dotColors = ['#22C55E', '#86EFAC', '#FCD34D', '#F97316', '#9CA3AF']
              return (
                <div
                  key={i}
                  className={`grid grid-cols-[1fr_180px_90px] gap-0 items-center px-4 py-3 bg-white ${!isLast ? 'border-b' : ''}`}
                  style={{ borderColor: border }}
                >
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: dotColors[i] ?? '#9CA3AF' }} />
                    <Input
                      value={tier.label}
                      onChange={e => setTier(i, 'label', e.target.value)}
                      className="h-7 text-sm font-medium border-0 bg-transparent focus-visible:ring-0 px-0 w-28"
                    />
                  </div>
                  <div>
                    {isLast ? (
                      <span className="text-sm text-[#9CA3AF] pl-2">cualquier valor</span>
                    ) : (
                      <ClpInput
                        value={tier.min}
                        onChange={v => setTier(i, 'min', v)}
                      />
                    )}
                  </div>
                  <div className="flex items-center justify-end gap-1.5">
                    <Input
                      type="number" min={0} max={40}
                      value={tier.points}
                      onChange={e => setTier(i, 'points', parseInt(e.target.value) || 0)}
                      className="h-8 w-16 text-center text-sm font-bold"
                      style={{ color: blue }}
                    />
                    <span className="text-xs text-[#9CA3AF]">pts</span>
                  </div>
                </div>
              )
            })}
          </div>

          {/* DICOM points */}
          <div className="mt-4 grid grid-cols-2 gap-3">
            {([
              { field: 'dicom_clean_pts' as const, label: 'DICOM Limpio', color: '#DCFCE7', textColor: '#166534', dot: '#22C55E', description: 'Sin deudas registradas' },
              { field: 'dicom_has_debt_pts' as const, label: 'DICOM con Deuda', color: '#FEF3C7', textColor: '#92400E', dot: '#F59E0B', description: 'Deuda ≤ límite aceptable' },
            ]).map(({ field, label, color, textColor, dot, description }) => (
              <div key={field} className="rounded-xl border p-4 bg-white" style={{ borderColor: border }}>
                <div className="flex items-center gap-1.5 mb-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: dot }} />
                  <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: textColor }}>{label}</span>
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <Input
                    type="number" min={0} max={20}
                    value={cfg.scoring_config?.[field] ?? DEFAULT_SCORING_CONFIG[field]}
                    onChange={e => setScoringPts(field, parseInt(e.target.value) || 0)}
                    className="h-9 w-20 text-center text-lg font-bold"
                    style={{ color: textColor }}
                  />
                  <div>
                    <span className="text-sm font-semibold text-[#9CA3AF]">/ 20 pts</span>
                    <p className="text-xs text-[#9CA3AF]">{description}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Score summary preview */}
          <div className="mt-4 rounded-xl p-4 border" style={{ borderColor: border, background: '#F8FAFC' }}>
            <p className="text-[11px] font-bold uppercase tracking-widest text-[#6B7280] mb-3">Máximos por componente</p>
            <div className="flex flex-wrap gap-2 text-xs">
              {[
                { label: 'Sueldo', max: Math.max(...(cfg.scoring_config?.income_tiers ?? DEFAULT_SCORING_CONFIG.income_tiers).map(t => t.points)), color: '#1A56DB' },
                { label: 'DICOM', max: cfg.scoring_config?.dicom_clean_pts ?? 20, color: '#22C55E' },
                { label: 'Perfil clave', max: 25, color: '#8B5CF6' },
                { label: 'Engagement', max: 15, color: '#F59E0B' },
              ].map(({ label, max, color }) => (
                <span key={label} className="inline-flex items-center gap-1 rounded-md px-2 py-1 border font-semibold" style={{ borderColor: `${color}40`, background: `${color}10`, color }}>
                  {label}: {max} pts
                </span>
              ))}
              <span className="inline-flex items-center gap-1 rounded-md px-2 py-1 border font-bold" style={{ borderColor: '#11182720', background: '#11182708', color: '#111827' }}>
                Total máx: {Math.max(...(cfg.scoring_config?.income_tiers ?? DEFAULT_SCORING_CONFIG.income_tiers).map(t => t.points)) + (cfg.scoring_config?.dicom_clean_pts ?? 20) + 25 + 15} pts
              </span>
            </div>
          </div>
        </div>
      </div>
    ),

    // ── TAB 2: FIELD WEIGHTS ──────────────────────────────────────────────────
    weights: (
      <div className="space-y-6">
        <div>
          <SectionLabel>Puntos por campo recopilado</SectionLabel>
          <p className="text-sm text-[#6B7280] mb-6">
            Cada vez que el agente obtiene un dato del lead, suma estos puntos al score. Un lead con buena renta y datos completos puede calificar aunque apenas haya conversado.
          </p>
          <div className="space-y-3">
            {([
              { key: 'name',           label: 'Nombre',          hint: 'Identificación básica' },
              { key: 'phone',          label: 'Teléfono',         hint: 'Canal de contacto' },
              { key: 'email',          label: 'Email',            hint: 'Seguimiento digital' },
              { key: 'location',       label: 'Ubicación',        hint: 'Filtro de propiedades' },
              { key: 'budget',         label: 'Presupuesto',      hint: 'Intención de compra' },
              { key: 'monthly_income', label: 'Renta mensual',    hint: 'Amplificado por score financiero' },
              { key: 'dicom_status',   label: 'Estado DICOM',     hint: 'Determinante para calificación' },
            ] as const).map(({ key, label, hint }) => {
              const val = cfg.field_weights[key]
              return (
                <div
                  key={key}
                  className="flex items-center gap-3 rounded-xl border bg-white px-4 py-3 sm:px-5 sm:py-4"
                  style={{ borderColor: border }}
                >
                  <div className="w-28 sm:w-40 shrink-0">
                    <p className="text-sm font-semibold text-[#111827]">{label}</p>
                    <p className="text-xs text-[#9CA3AF]">{hint}</p>
                  </div>
                  <div className="flex-1 h-2.5 rounded-full overflow-hidden" style={{ background: '#E5E7EB' }}>
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{
                        width: `${Math.min(100, val)}%`,
                        background: `linear-gradient(90deg, #93C5FD, ${blue})`,
                      }}
                    />
                  </div>
                  <div className="relative w-24 shrink-0">
                    <Input
                      type="number" min={0} max={100} value={val}
                      onChange={(e) => {
                        const n = Math.min(100, Math.max(0, parseInt(e.target.value) || 0))
                        set('field_weights', { ...cfg.field_weights, [key]: n })
                      }}
                      className="text-center pr-8 h-9 text-sm"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[#9CA3AF]">pts</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
        <div className="rounded-xl border overflow-hidden" style={{ borderColor: border }}>
          <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: border, background: '#fff' }}>
            <div>
              <p className="text-xs font-bold uppercase tracking-widest" style={{ color: blue }}>Puntaje máximo alcanzable</p>
              <p className="text-xs text-[#6B7280] mt-0.5">Solo contando los datos recopilados (sin comportamiento ni etapa)</p>
            </div>
            <span className="text-2xl font-bold" style={{ color: blue }}>
              {Object.values(cfg.field_weights).reduce((a, b) => a + b, 0)} pts
            </span>
          </div>
          <div className="px-5 py-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Para ser Frío',       threshold: cfg.cold_max_score,      color: '#60A5FA' },
              { label: 'Para ser Tibio',       threshold: cfg.warm_max_score,      color: '#F59E0B' },
              { label: 'Para ser Caliente',    threshold: cfg.hot_min_score,       color: '#F97316' },
              { label: 'Para estar Calificado', threshold: cfg.qualified_min_score, color: '#22C55E' },
            ].map(({ label, threshold, color }) => {
              const total = Object.values(cfg.field_weights).reduce((a, b) => a + b, 0)
              const reachable = total >= threshold
              return (
                <div key={label} className="rounded-lg border p-3" style={{ borderColor: border }}>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-[#9CA3AF] mb-1">{label}</p>
                  <p className="text-lg font-bold" style={{ color }}>{threshold} pts</p>
                  <p className="text-[10px] mt-1" style={{ color: reachable ? '#16A34A' : '#DC2626' }}>
                    {reachable ? `✓ alcanzable con datos` : `✗ requiere comportamiento`}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    ),

    // ── TAB 3: AGENT PRIORITY ─────────────────────────────────────────────────
    agent: (
      <div className="space-y-6">
        {/* Timezone selector */}
        <div>
          <SectionLabel>Zona horaria del agente</SectionLabel>
          <p className="text-sm text-[#6B7280] mb-4">
            El agente usa esta zona horaria para interpretar fechas como "mañana" y al crear citas.
          </p>
          <select
            value={cfg.timezone}
            onChange={e => set('timezone', e.target.value)}
            className="w-full rounded-lg border px-3 py-2 text-sm text-[#111827] focus:outline-none focus:ring-2"
            style={{ borderColor: border, background: '#fff', focusRingColor: blue }}
          >
            <option value="America/Santiago">🇨🇱 América/Santiago (Chile)</option>
            <option value="America/Lima">🇵🇪 América/Lima (Perú)</option>
            <option value="America/Bogota">🇨🇴 América/Bogotá (Colombia)</option>
            <option value="America/Buenos_Aires">🇦🇷 América/Buenos Aires (Argentina)</option>
            <option value="America/Mexico_City">🇲🇽 América/Ciudad de México</option>
            <option value="America/Guayaquil">🇪🇨 América/Guayaquil (Ecuador)</option>
            <option value="America/Caracas">🇻🇪 América/Caracas (Venezuela)</option>
            <option value="Europe/Madrid">🇪🇸 Europa/Madrid (España)</option>
            <option value="UTC">🌐 UTC</option>
          </select>
        </div>

        <hr style={{ borderColor: border }} />

        <div>
          <SectionLabel>Orden de preguntas del agente</SectionLabel>
          <p className="text-sm text-[#6B7280] mb-1">
            Arrastra los campos para cambiar el orden en que el agente los solicita. Esto se escribe directamente en el prompt de este broker.
          </p>
          <p className="text-xs text-[#9CA3AF] mb-6">
            💡 El agente nunca vuelve a preguntar un dato que el lead ya proporcionó.
          </p>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={cfg.field_priority} strategy={verticalListSortingStrategy}>
              <div className="space-y-2">
                {cfg.field_priority.map((id, index) => (
                  <SortableField key={id} id={id} index={index} />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        </div>

        {/* Preview of prompt section */}
        <div className="rounded-xl border overflow-hidden" style={{ borderColor: border }}>
          <div className="px-5 py-3 border-b flex items-center gap-2" style={{ borderColor: border, background: '#F9FAFB' }}>
            <span className="text-[10px] font-bold uppercase tracking-widest text-[#9CA3AF]">Vista previa del prompt generado</span>
          </div>
          <div className="px-5 py-4 font-mono text-xs text-[#374151] leading-relaxed" style={{ background: '#FAFAFA' }}>
            <span className="font-bold text-[#1A56DB]">## DATOS A RECOPILAR (en este orden)</span>
            {cfg.field_priority.map((id, i) => (
              <div key={id}>
                <span className="text-[#6B7280]">{i + 1}.</span>{' '}
                <span>{FIELD_META[id]?.label ?? id}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    ),

    // ── TAB 4: PROMPT IA (admin only) ─────────────────────────────────────────
    prompt: (
      <div className="space-y-8">

        {/* ── Multi-agent section ──────────────────────────────────────────── */}
        {agentPrompts && (
          <div>
            {/* Status banner */}
            <div
              className="flex items-center gap-3 rounded-xl px-4 py-3 border mb-6"
              style={{ background: '#F0FDF4', borderColor: '#86EFAC' }}
            >
              <span className="text-lg">✅</span>
              <div>
                <p className="text-sm font-semibold" style={{ color: '#166534' }}>
                  Multi-agente activo — los prompts de abajo son los que usa Sofía
                </p>
                <p className="text-xs mt-0.5" style={{ color: '#6B7280' }}>
                  Cada agente usa su propio prompt según la etapa del lead. Deja el campo vacío para usar el prompt por defecto.
                </p>
              </div>
            </div>

            <SectionLabel>Prompts por agente</SectionLabel>
            <p className="text-sm text-[#6B7280] mb-5">
              Cada agente usa un prompt especializado según la etapa del lead. Deja el campo vacío para usar el prompt por defecto del sistema.
            </p>

            {/* Agent prompt editors */}
            {([
              {
                key: 'qualifier' as const,
                label: 'QualifierAgent',
                subtitle: 'Etapas: entrada → perfilamiento',
                description: 'Recopila datos del lead (nombre, teléfono, email, renta, DICOM) y decide si califica para agendar.',
                color: '#1A56DB',
                bg: '#EBF2FF',
              },
              {
                key: 'scheduler' as const,
                label: 'SchedulerAgent',
                subtitle: 'Etapa: calificacion_financiera',
                description: 'Convierte leads calificados en visitas agendadas. Usa herramientas de calendario.',
                color: '#7C3AED',
                bg: '#F5F3FF',
              },
              {
                key: 'follow_up' as const,
                label: 'FollowUpAgent',
                subtitle: 'Etapas: potencial, agendado',
                description: 'Nurturing de leads potenciales y acompañamiento post-agendamiento.',
                color: '#059669',
                bg: '#F0FDF4',
              },
            ]).map(({ key, label, subtitle, description, color, bg }) => {
              const defaultPrompt = agentPrompts[key].default
              const customVal = agentCustom[key]
              return (
                <div key={key} className="rounded-xl border overflow-hidden mb-4" style={{ borderColor: border }}>
                  {/* Header */}
                  <div className="flex items-start justify-between px-5 py-3 border-b" style={{ background: bg, borderColor: border }}>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold uppercase tracking-widest" style={{ color }}>{label}</span>
                        {customVal
                          ? <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded" style={{ background: color, color: '#fff' }}>personalizado</span>
                          : <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded border" style={{ borderColor: color, color }}>por defecto</span>
                        }
                      </div>
                      <p className="text-xs text-[#6B7280] mt-0.5">{subtitle} — {description}</p>
                    </div>
                    {customVal && (
                      <button
                        onClick={() => setAgentCustom(prev => ({ ...prev, [key]: '' }))}
                        className="text-xs text-[#EF4444] hover:underline shrink-0 ml-3"
                      >
                        Restablecer
                      </button>
                    )}
                  </div>

                  {/* Editor */}
                  <div className="p-4" style={{ background: '#FAFAFA' }}>
                    <Textarea
                      value={customVal || defaultPrompt}
                      onChange={(e) => {
                        const val = e.target.value
                        setAgentCustom(prev => ({ ...prev, [key]: val === defaultPrompt ? '' : val }))
                      }}
                      className="min-h-[220px] font-mono text-xs resize-y"
                      style={{ borderColor: border }}
                    />
                    <p className="text-xs text-[#9CA3AF] mt-1.5">
                      {customVal
                        ? `Prompt personalizado · ${customVal.length} caracteres`
                        : 'Mostrando prompt por defecto — edita para personalizar'}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        )}

      </div>
    ),

    // ── TAB 5: CALENDARIO ─────────────────────────────────────────────────────
    calendar: (
      <div className="space-y-6">
        <div>
          <SectionLabel>Calendario</SectionLabel>
        </div>

        <CalendarSection />

        {/* ── Availability Slots ────────────────────────────────────────── */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <SectionLabel>Horario de Disponibilidad</SectionLabel>
          </div>
          <p className="text-sm text-[#6B7280] mb-5">
            Define los días y horarios en que el agente puede agendar citas. Si tienes varios agentes, todos comparten este horario y se pueden agendar múltiples citas en el mismo tramo.
          </p>

          {slotsLoading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-5 w-5 animate-spin text-[#9CA3AF]" />
            </div>
          ) : (
            <div className="rounded-xl border overflow-hidden" style={{ borderColor: border }}>
              {/* Day columns header */}
              <div className="grid grid-cols-7 border-b" style={{ borderColor: border, background: '#F8FAFC' }}>
                {['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'].map((d, i) => (
                  <div key={i} className="px-2 py-2.5 text-center" style={{ borderRight: i < 6 ? `1px solid ${border}` : undefined }}>
                    <span className="text-[11px] font-bold uppercase tracking-wider text-[#6B7280]">{d}</span>
                  </div>
                ))}
              </div>
              {/* Day columns body */}
              <div className="grid grid-cols-7 bg-white min-h-[120px]">
                {[0, 1, 2, 3, 4, 5, 6].map((dayIdx) => {
                  const daySlots = slots.filter(s => s.day_of_week === dayIdx && s.is_active)
                  return (
                    <div
                      key={dayIdx}
                      className="p-2 flex flex-col gap-1.5"
                      style={{ borderRight: dayIdx < 6 ? `1px solid ${border}` : undefined, minHeight: 100 }}
                    >
                      {daySlots.map(slot => (
                        <button
                          key={slot.id}
                          onClick={() => {
                            setSlotDialog({ open: true, editing: slot, day: slot.day_of_week })
                            setSlotForm({
                              day_of_week: slot.day_of_week,
                              start_time: slot.start_time,
                              end_time: slot.end_time,
                              slot_duration_minutes: slot.slot_duration_minutes,
                            })
                          }}
                          className="w-full text-left rounded-lg px-2 py-1.5 text-xs font-semibold transition-colors hover:opacity-80"
                          style={{ background: blueLt, color: blue }}
                        >
                          <div className="flex items-center gap-1">
                            <Clock className="h-2.5 w-2.5 shrink-0" />
                            <span>{slot.start_time}–{slot.end_time}</span>
                          </div>
                          <div className="text-[10px] font-normal opacity-70 mt-0.5">{slot.slot_duration_minutes}min/cita</div>
                        </button>
                      ))}
                      <button
                        onClick={() => {
                          setSlotDialog({ open: true, editing: null, day: dayIdx })
                          setSlotForm({ day_of_week: dayIdx, start_time: '09:00', end_time: '18:00', slot_duration_minutes: 60 })
                        }}
                        className="w-full flex items-center justify-center rounded-lg py-1.5 text-xs text-[#9CA3AF] border border-dashed transition-colors hover:border-[#1A56DB] hover:text-[#1A56DB]"
                        style={{ borderColor: '#D1D9E6' }}
                      >
                        <Plus className="h-3 w-3" />
                      </button>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Slot create/edit dialog */}
        <Dialog open={slotDialog.open} onOpenChange={(open) => setSlotDialog(d => ({ ...d, open }))}>
          <DialogContent className="sm:max-w-sm">
            <DialogHeader>
              <DialogTitle>{slotDialog.editing ? 'Editar franja horaria' : 'Nueva franja horaria'}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-1.5">
                <Label>Día de la semana</Label>
                <select
                  value={slotForm.day_of_week}
                  onChange={e => setSlotForm(f => ({ ...f, day_of_week: parseInt(e.target.value) }))}
                  className="w-full rounded-lg border px-3 py-2 text-sm"
                  style={{ borderColor: border }}
                >
                  {['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'].map((d, i) => (
                    <option key={i} value={i}>{d}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Hora inicio</Label>
                  <Input
                    type="time"
                    value={slotForm.start_time}
                    onChange={e => setSlotForm(f => ({ ...f, start_time: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Hora fin</Label>
                  <Input
                    type="time"
                    value={slotForm.end_time}
                    onChange={e => setSlotForm(f => ({ ...f, end_time: e.target.value }))}
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label>Duración por cita (minutos)</Label>
                <Input
                  type="number"
                  min={15}
                  max={480}
                  step={15}
                  value={slotForm.slot_duration_minutes}
                  onChange={e => setSlotForm(f => ({ ...f, slot_duration_minutes: parseInt(e.target.value) || 60 }))}
                />
                <p className="text-xs text-[#9CA3AF]">
                  Con este horario caben {Math.floor(
                    (parseInt(slotForm.end_time.split(':')[0]) * 60 + parseInt(slotForm.end_time.split(':')[1]) -
                     parseInt(slotForm.start_time.split(':')[0]) * 60 - parseInt(slotForm.start_time.split(':')[1]))
                    / slotForm.slot_duration_minutes
                  )} citas por día
                </p>
              </div>
            </div>
            <DialogFooter className="gap-2">
              {slotDialog.editing && (
                <Button
                  variant="outline"
                  size="sm"
                  className="text-rose-600 border-rose-200 hover:bg-rose-50 mr-auto"
                  disabled={slotSaving}
                  onClick={async () => {
                    if (!slotDialog.editing) return
                    setSlotSaving(true)
                    try {
                      await settingsService.deleteAvailabilitySlot(slotDialog.editing.id)
                      setSlots(prev => prev.filter(s => s.id !== slotDialog.editing!.id))
                      setSlotDialog(d => ({ ...d, open: false }))
                      toast.success('Franja eliminada')
                    } catch (e) {
                      toast.error(getErrorMessage(e))
                    } finally {
                      setSlotSaving(false)
                    }
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5 mr-1" /> Eliminar
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={() => setSlotDialog(d => ({ ...d, open: false }))}>
                Cancelar
              </Button>
              <Button
                size="sm"
                disabled={slotSaving}
                style={{ background: blue, color: '#fff' }}
                onClick={async () => {
                  setSlotSaving(true)
                  try {
                    if (slotDialog.editing) {
                      const updated = await settingsService.updateAvailabilitySlot(slotDialog.editing.id, slotForm)
                      setSlots(prev => prev.map(s => s.id === updated.id ? updated : s))
                      toast.success('Franja actualizada')
                    } else {
                      const created = await settingsService.createAvailabilitySlot(slotForm)
                      setSlots(prev => [...prev, created])
                      toast.success('Franja creada')
                    }
                    setSlotDialog(d => ({ ...d, open: false }))
                  } catch (e) {
                    toast.error(getErrorMessage(e))
                  } finally {
                    setSlotSaving(false)
                  }
                }}
              >
                {slotSaving && <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />}
                {slotDialog.editing ? 'Guardar cambios' : 'Crear franja'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* ── Appointment Blocks ────────────────────────────────────────── */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <SectionLabel>Bloqueos de Agenda</SectionLabel>
              <p className="text-sm text-[#6B7280]">Períodos donde no se pueden agendar citas (vacaciones, reuniones, etc.)</p>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setBlockForm({ start_time: '', end_time: '', reason: '' })
                setBlockDialog(true)
              }}
              style={{ borderColor: border }}
            >
              <Plus className="h-3.5 w-3.5 mr-1.5" />
              Agregar bloqueo
            </Button>
          </div>

          {blocks.length === 0 ? (
            <div className="rounded-xl border border-dashed p-6 text-center" style={{ borderColor: border }}>
              <p className="text-sm text-[#9CA3AF]">Sin bloqueos configurados</p>
            </div>
          ) : (
            <div className="rounded-xl border overflow-hidden" style={{ borderColor: border }}>
              {blocks.map((block, i) => (
                <div
                  key={block.id}
                  className="flex items-center gap-3 px-4 py-3 bg-white"
                  style={{ borderBottom: i < blocks.length - 1 ? `1px solid ${border}` : undefined }}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[#111827]">{block.reason}</p>
                    <p className="text-xs text-[#9CA3AF]">
                      {new Date(block.start_time).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' })}
                      {' — '}
                      {new Date(block.end_time).toLocaleString('es-CL', { dateStyle: 'short', timeStyle: 'short' })}
                    </p>
                  </div>
                  <button
                    className="shrink-0 p-1.5 rounded-lg text-[#9CA3AF] hover:text-rose-500 hover:bg-rose-50 transition-colors"
                    onClick={async () => {
                      try {
                        await settingsService.deleteBlock(block.id)
                        setBlocks(prev => prev.filter(b => b.id !== block.id))
                        toast.success('Bloqueo eliminado')
                      } catch (e) {
                        toast.error(getErrorMessage(e))
                      }
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Block create dialog */}
        <Dialog open={blockDialog} onOpenChange={setBlockDialog}>
          <DialogContent className="sm:max-w-sm">
            <DialogHeader>
              <DialogTitle>Nuevo bloqueo de agenda</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="space-y-1.5">
                <Label>Motivo</Label>
                <Input
                  value={blockForm.reason}
                  onChange={e => setBlockForm(f => ({ ...f, reason: e.target.value }))}
                  placeholder="Ej: Vacaciones, Reunión de equipo"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Desde</Label>
                  <Input
                    type="datetime-local"
                    value={blockForm.start_time}
                    onChange={e => setBlockForm(f => ({ ...f, start_time: e.target.value }))}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Hasta</Label>
                  <Input
                    type="datetime-local"
                    value={blockForm.end_time}
                    onChange={e => setBlockForm(f => ({ ...f, end_time: e.target.value }))}
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" size="sm" onClick={() => setBlockDialog(false)}>Cancelar</Button>
              <Button
                size="sm"
                disabled={blockSaving || !blockForm.reason || !blockForm.start_time || !blockForm.end_time}
                style={{ background: blue, color: '#fff' }}
                onClick={async () => {
                  setBlockSaving(true)
                  try {
                    const created = await settingsService.createBlock(blockForm)
                    setBlocks(prev => [...prev, created])
                    setBlockDialog(false)
                    toast.success('Bloqueo creado')
                  } catch (e) {
                    toast.error(getErrorMessage(e))
                  } finally {
                    setBlockSaving(false)
                  }
                }}
              >
                {blockSaving && <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />}
                Crear bloqueo
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    ),
  }

  return (
    <div className="flex flex-col h-full min-h-screen" style={{ background: bg }}>
      {/* ── Page header ─────────────────────────────────────────────────────── */}
      <div className="px-4 sm:px-8 pt-4 sm:pt-8 pb-0">
        <div className="mb-1 flex items-center gap-1.5 text-xs text-[#9CA3AF]">
          <span>Admin</span>
          <span>›</span>
          <span style={{ color: blue }} className="font-medium">Configuración</span>
        </div>
        <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-[#111827] tracking-tight">Configuración del agente</h1>
            <p className="text-sm text-[#6B7280] mt-1">Personaliza cómo Sofía califica e interactúa con tus leads</p>
          </div>
          <Button
            onClick={handleSave}
            disabled={isSaving}
            className="shrink-0"
            style={{ background: blue, color: '#fff' }}
          >
            {isSaving
              ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Guardando…</>
              : <><Save className="mr-2 h-4 w-4" />Guardar cambios</>
            }
          </Button>
        </div>

        {/* ── Custom tab bar ──────────────────────────────────────────────── */}
        <div className="relative flex gap-1 border-b overflow-x-auto" style={{ borderColor: border }}>
          {TABS.filter(tab => (tab.id !== 'prompt' && tab.id !== 'calendar') || isAdmin).map((tab) => {
            const Icon = tab.icon
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                ref={(el) => { tabRefs.current[tab.id] = el }}
                onClick={() => setActiveTab(tab.id)}
                className="flex items-center gap-2 px-5 py-3 text-sm font-medium transition-colors relative"
                style={{ color: active ? blue : '#6B7280' }}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            )
          })}
          {/* Sliding indicator */}
          <div
            className="absolute bottom-0 h-0.5 rounded-full transition-all duration-300 ease-out"
            style={{ background: blue, left: indicatorStyle.left, width: indicatorStyle.width }}
          />
        </div>
      </div>

      {/* ── Tab content ─────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 sm:px-8 py-4 sm:py-8">
        <div className="max-w-3xl">
          {tabContent[activeTab]}
        </div>
      </div>
    </div>
  )
}

// ── Small helper component ────────────────────────────────────────────────────
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#9CA3AF] mb-2">{children}</h2>
  )
}
