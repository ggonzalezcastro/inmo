import { useEffect, useRef, useState } from 'react'
import {
  X,
  MessageSquare,
  FileText,
  ChevronRight,
  ExternalLink,
  Bot,
  User,
  Phone,
  RefreshCw,
  Copy,
  Check,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/shared/lib/utils'
import { formatRelativeTime, formatDate, formatCurrency } from '@/shared/lib/utils'
import { Button } from '@/shared/components/ui/button'
import { ScoreBadge } from '@/shared/components/common/ScoreBadge'
import { StatusBadge } from '@/shared/components/common/StatusBadge'
import { QualificationBadge } from '@/shared/components/common/QualificationBadge'
import { LoadingSpinner } from '@/shared/components/common/LoadingSpinner'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu'
import { PIPELINE_STAGES, DICOM_CONFIG } from '@/shared/lib/constants'
import { chatService, type ChatMessage } from '../services/chat.service'
import { getErrorMessage } from '@/shared/types/api'
import type { Lead } from '@/features/leads/types'

// ── Types ───────────────────────────────────────────────────────────────────

interface LeadDrawerProps {
  lead: Lead | null
  onClose: () => void
  onMoveStage: (lead: Lead, newStage: string) => void
}

type Tab = 'chat' | 'details'

// ── Sub-components ───────────────────────────────────────────────────────────

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const isCustomer = msg.sender_type === 'customer'
  const time = msg.created_at ? formatRelativeTime(msg.created_at) : ''

  return (
    <div className={cn('flex gap-2 mb-3', isCustomer ? 'flex-row' : 'flex-row-reverse')}>
      {/* Avatar */}
      <div
        className={cn(
          'w-7 h-7 rounded-full shrink-0 flex items-center justify-center mt-0.5',
          isCustomer
            ? 'bg-[#F0F4F8] border border-[#D1D9E6]'
            : 'bg-[#1A56DB]'
        )}
      >
        {isCustomer ? (
          <User className="h-3.5 w-3.5 text-[#6B7280]" />
        ) : (
          <Bot className="h-3.5 w-3.5 text-white" />
        )}
      </div>

      {/* Bubble */}
      <div className={cn('max-w-[75%] space-y-1', isCustomer ? 'items-start' : 'items-end')}>
        <div
          className={cn(
            'px-3 py-2 rounded-2xl text-sm leading-relaxed',
            isCustomer
              ? 'bg-[#F0F4F8] text-[#111827] rounded-tl-sm border border-[#E2EAF4]'
              : 'bg-[#1A56DB] text-white rounded-tr-sm'
          )}
        >
          {msg.message_text}
        </div>
        <p
          className={cn(
            'text-[10px] text-muted-foreground px-1',
            isCustomer ? 'text-left' : 'text-right'
          )}
        >
          {isCustomer ? 'Lead' : msg.ai_response_used ? 'Sofía IA' : 'Agente'} · {time}
        </p>
      </div>
    </div>
  )
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-2.5 border-b border-[#F0F4F8] last:border-0">
      <span className="text-xs text-muted-foreground uppercase tracking-wide font-medium">
        {label}
      </span>
      <span className="text-sm font-medium text-foreground text-right max-w-[55%] break-words">
        {value ?? <span className="text-muted-foreground">—</span>}
      </span>
    </div>
  )
}

// ── Main Component ───────────────────────────────────────────────────────────

export function LeadDrawer({ lead, onClose, onMoveStage }: LeadDrawerProps) {
  const [tab, setTab] = useState<Tab>('chat')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loadingChat, setLoadingChat] = useState(false)
  const [copied, setCopied] = useState(false)
  const chatBottomRef = useRef<HTMLDivElement>(null)
  const drawerRef = useRef<HTMLDivElement>(null)

  // ── Fetch messages when lead changes ──────────────────────────────────────
  useEffect(() => {
    if (!lead) return
    setMessages([])
    setTab('chat')
    setLoadingChat(true)
    chatService
      .getMessages(lead.id)
      .then(setMessages)
      .catch((err) => toast.error(getErrorMessage(err)))
      .finally(() => setLoadingChat(false))
  }, [lead?.id])

  // ── Scroll to bottom of chat ──────────────────────────────────────────────
  useEffect(() => {
    if (tab === 'chat' && chatBottomRef.current) {
      chatBottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, tab])

  // ── Close on Escape ───────────────────────────────────────────────────────
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  const handleCopyPhone = () => {
    if (!lead) return
    navigator.clipboard.writeText(lead.phone).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  if (!lead) return null

  const meta = lead.lead_metadata ?? {}
  const dicomCfg = meta.dicom_status ? DICOM_CONFIG[meta.dicom_status as keyof typeof DICOM_CONFIG] : null
  const otherStages = PIPELINE_STAGES.filter((s) => s.key !== lead.pipeline_stage)

  return (
    <>
      {/* ── Backdrop ──────────────────────────────────────────────────────── */}
      <div
        className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[1px]"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* ── Drawer panel ──────────────────────────────────────────────────── */}
      <div
        ref={drawerRef}
        className="fixed right-0 top-0 bottom-0 z-50 w-[400px] bg-white border-l border-[#D1D9E6] shadow-2xl flex flex-col"
        style={{ animation: 'slideInRight 0.22s ease-out' }}
      >
        {/* ── Header ──────────────────────────────────────────────────────── */}
        <div className="px-5 pt-5 pb-4 border-b border-[#E2EAF4]">
          {/* Top row: close + actions */}
          <div className="flex items-center justify-between mb-3">
            <button
              onClick={onClose}
              className="w-7 h-7 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-[#F0F4F8] transition-colors"
              aria-label="Cerrar panel"
            >
              <X className="h-4 w-4" />
            </button>

            <div className="flex items-center gap-1.5">
              <button
                onClick={handleCopyPhone}
                title="Copiar teléfono"
                className="h-7 px-2 rounded-lg flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-[#F0F4F8] transition-colors"
              >
                {copied ? (
                  <Check className="h-3.5 w-3.5 text-emerald-500" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
                {copied ? 'Copiado' : lead.phone}
              </button>

              <a
                href={`/leads`}
                className="h-7 px-2 rounded-lg flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground hover:bg-[#F0F4F8] transition-colors"
                title="Ver en Leads"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Leads
              </a>
            </div>
          </div>

          {/* Lead name + badges */}
          <div className="space-y-2">
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <h2 className="text-[17px] font-bold text-[#111827] leading-tight truncate">
                  {lead.name}
                </h2>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <Phone className="h-3 w-3 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">{lead.phone}</span>
                </div>
              </div>
              <ScoreBadge score={lead.lead_score} />
            </div>

            <div className="flex flex-wrap gap-1.5">
              <StatusBadge status={lead.status} />
              {meta.calificacion && (
                <QualificationBadge calificacion={meta.calificacion as 'CALIFICADO' | 'POTENCIAL' | 'NO_CALIFICADO'} />
              )}
              {lead.last_contacted && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-[#F0F4F8] text-[#6B7280] border border-[#D1D9E6]">
                  Contactado {formatRelativeTime(lead.last_contacted)}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* ── Tabs ────────────────────────────────────────────────────────── */}
        <div className="flex border-b border-[#E2EAF4]">
          {([
            { id: 'chat' as Tab, label: 'Chat', icon: MessageSquare },
            { id: 'details' as Tab, label: 'Detalles', icon: FileText },
          ] as const).map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={cn(
                'flex items-center gap-1.5 px-5 py-3 text-sm font-medium border-b-2 transition-colors',
                tab === id
                  ? 'border-[#1A56DB] text-[#1A56DB]'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>

        {/* ── Content ─────────────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {/* Chat tab */}
          {tab === 'chat' && (
            <div className="p-4">
              {loadingChat ? (
                <div className="flex items-center justify-center py-12">
                  <LoadingSpinner size="md" />
                </div>
              ) : messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="w-12 h-12 rounded-2xl bg-[#EBF2FF] border border-[#BFCFFF] flex items-center justify-center mb-3">
                    <MessageSquare className="h-6 w-6 text-[#1A56DB]" />
                  </div>
                  <p className="text-sm font-medium text-foreground mb-1">Sin conversación</p>
                  <p className="text-xs text-muted-foreground">
                    Este lead aún no tiene mensajes registrados
                  </p>
                </div>
              ) : (
                <>
                  {messages.map((msg) => (
                    <ChatBubble key={msg.id} msg={msg} />
                  ))}
                  <div ref={chatBottomRef} />
                </>
              )}
            </div>
          )}

          {/* Details tab */}
          {tab === 'details' && (
            <div className="px-5 py-4">
              {/* Profile section */}
              <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">
                Perfil
              </p>
              <div className="mb-5">
                <DetailRow label="Ubicación" value={meta.location as string} />
                <DetailRow label="Propósito" value={
                  meta.purpose === 'vivienda' ? 'Vivienda propia'
                    : meta.purpose === 'inversion' ? 'Inversión'
                    : (meta.purpose as string | undefined) ?? null
                } />
                <DetailRow label="Tipo de propiedad" value={meta.property_type as string} />
                <DetailRow label="Dormitorios" value={meta.rooms as string} />
                <DetailRow label="Plazo" value={meta.timeline as string} />
              </div>

              {/* Financial section */}
              <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">
                Financiero
              </p>
              <div className="mb-5">
                <DetailRow
                  label="Presupuesto"
                  value={meta.budget ? formatCurrency(Number(meta.budget)) : (meta.budget as string)}
                />
                <DetailRow
                  label="Ingreso mensual"
                  value={meta.monthly_income ? formatCurrency(meta.monthly_income) : null}
                />
                <DetailRow
                  label="Residencia"
                  value={meta.residency_status === 'residente' ? 'Residente' : meta.residency_status === 'extranjero' ? 'Extranjero' : ((meta.residency_status as string | undefined) ?? null)}
                />
                {dicomCfg && (
                  <DetailRow
                    label="DICOM"
                    value={
                      <span className={cn('text-sm font-medium', dicomCfg.className)}>
                        {dicomCfg.label}
                      </span>
                    }
                  />
                )}
              </div>

              {/* Record section */}
              <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-widest mb-2">
                Registro
              </p>
              <div>
                <DetailRow label="Creado" value={formatDate(lead.created_at)} />
                <DetailRow label="Email" value={lead.email} />
                <DetailRow label="ID" value={`#${lead.id}`} />
                {lead.tags && lead.tags.length > 0 && (
                  <DetailRow
                    label="Tags"
                    value={
                      <div className="flex flex-wrap gap-1 justify-end">
                        {lead.tags.map((tag) => (
                          <span
                            key={tag}
                            className="px-1.5 py-0.5 rounded text-[10px] bg-[#EBF2FF] text-[#1A56DB] border border-[#BFCFFF]"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    }
                  />
                )}
              </div>
            </div>
          )}
        </div>

        {/* ── Footer actions ─────────────────────────────────────────────── */}
        <div className="px-4 py-3 border-t border-[#E2EAF4] bg-[#FAFBFD] flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="flex-1 justify-between h-9">
                <span className="flex items-center gap-1.5">
                  <RefreshCw className="h-3.5 w-3.5" />
                  Mover etapa
                </span>
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-52">
              {otherStages.map((s) => (
                <DropdownMenuItem
                  key={s.key}
                  onClick={() => {
                    onMoveStage(lead, s.key)
                    onClose()
                  }}
                >
                  {s.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          <a
            href={`/leads`}
            className="h-9 px-3 rounded-md flex items-center gap-1.5 text-sm font-medium bg-[#1A56DB] text-white hover:bg-[#1746c0] transition-colors"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            Ver lead
          </a>
        </div>
      </div>

      {/* Slide-in animation */}
      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0.8; }
          to   { transform: translateX(0);    opacity: 1;   }
        }
      `}</style>
    </>
  )
}
