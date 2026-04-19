import { useState, useEffect, useRef, useCallback } from 'react'
import { toast } from 'sonner'
import { conversationService, type ConversationLead } from '../services/conversation.service'
import { chatService, type ChatMessage } from '@/features/pipeline/services/chat.service'
import { pipelineService } from '@/features/pipeline/services/pipeline.service'
import { cn } from '@/shared/lib/utils'
import { useWebSocketEvent } from '@/shared/context/WebSocketContext'
import { useAuthStore } from '@/features/auth'
import {
  Bot, User, Search, Send, RefreshCw,
  MessageSquare, Inbox, ChevronDown,
  WifiOff, Phone, CheckCheck, Sparkles,
  UserCheck, ArrowRight, ArrowLeft, AlertTriangle, Wand2,
} from 'lucide-react'

// ── Constants ────────────────────────────────────────────────────────────────

const STAGES: { value: string; label: string; color: string }[] = [
  { value: 'entrada',                 label: 'Entrada',               color: '#94A3B8' },
  { value: 'perfilamiento',           label: 'Perfilamiento',         color: '#60A5FA' },
  { value: 'calificacion_financiera', label: 'Cal. Financiera',       color: '#A78BFA' },
  { value: 'potencial',               label: 'Potencial',             color: '#FB923C' },
  { value: 'agendado',                label: 'Agendado',              color: '#34D399' },
  { value: 'ganado',                  label: 'Ganado',                color: '#10B981' },
  { value: 'perdido',                 label: 'Perdido',               color: '#F87171' },
]

const CHANNEL_CFG: Record<string, { label: string; dot: string }> = {
  whatsapp:               { label: 'WhatsApp',  dot: '#22C55E' },
  telegram:               { label: 'Telegram',  dot: '#0EA5E9' },
  webchat:                { label: 'Web',        dot: '#8B5CF6' },
  'ChatProvider.WEBCHAT': { label: 'Web',        dot: '#8B5CF6' },
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return ''
  const diff = (Date.now() - new Date(dateStr).getTime()) / 1000
  if (diff < 60) return 'ahora'
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`
  return `${Math.floor(diff / 86400)}d`
}

function initials(name: string | null, phone: string): string {
  return (name ?? phone)
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0] ?? '')
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

// ── ConversationItem ──────────────────────────────────────────────────────────

function ConversationItem({
  lead,
  selected,
  onClick,
}: {
  lead: ConversationLead
  selected: boolean
  onClick: () => void
}) {
  const stage = STAGES.find((s) => s.value === lead.pipeline_stage)
  const ch = lead.channel ? (CHANNEL_CFG[lead.channel] ?? { label: lead.channel, dot: '#9CA3AF' }) : null

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left px-4 py-3.5 relative transition-all duration-150',
        'border-b border-[#EEF2F7]',
        selected
          ? 'bg-[#EBF2FF]'
          : 'hover:bg-[#F7F9FC]',
      )}
    >
      {/* Active indicator */}
      <div
        className={cn(
          'absolute left-0 top-0 bottom-0 w-[3px] rounded-r-full transition-all duration-200',
          selected ? 'bg-[#1A56DB]' : 'bg-transparent',
        )}
      />

      <div className="flex items-start gap-3 pl-1">
        {/* Avatar */}
        <div
          className={cn(
            'h-10 w-10 rounded-full flex items-center justify-center text-sm font-bold shrink-0 relative',
            lead.human_mode
              ? 'bg-[#DBEAFE] text-[#1D4ED8]'
              : 'bg-gradient-to-br from-[#E2EAF4] to-[#C7D7EC] text-[#374151]',
          )}
        >
          {initials(lead.name, lead.phone)}
          {lead.human_mode && (
            <span className="absolute -bottom-0.5 -right-0.5 h-4 w-4 rounded-full bg-[#1A56DB] flex items-center justify-center ring-2 ring-white">
              <User size={9} className="text-white" />
            </span>
          )}
        </div>

        <div className="flex-1 min-w-0">
          {/* Name + time */}
          <div className="flex items-center justify-between gap-2 mb-0.5">
            <span className={cn('text-sm font-semibold truncate', selected ? 'text-[#1A56DB]' : 'text-[#111827]')}>
              {lead.name ?? lead.phone}
            </span>
            <span className="text-[11px] text-[#9CA3AF] shrink-0 tabular-nums">
              {timeAgo(lead.last_message_at)}
            </span>
          </div>

          {/* Last message */}
          <p className="text-xs text-[#6B7280] truncate mb-2 leading-relaxed">
            {lead.last_message_direction === 'out' && (
              <CheckCheck size={10} className="inline mr-1 text-[#1A56DB]" />
            )}
            {lead.last_message ?? <span className="italic opacity-60">Sin mensajes</span>}
          </p>

          {/* Tags row */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {/* Channel dot */}
            {ch && (
              <span className="flex items-center gap-1 text-[10px] text-[#6B7280]">
                <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: ch.dot }} />
                {ch.label}
              </span>
            )}

            {/* Stage pill */}
            {stage && (
              <span
                className="text-[10px] font-medium px-1.5 py-0.5 rounded-md"
                style={{ background: stage.color + '18', color: stage.color }}
              >
                {stage.label}
              </span>
            )}

            {/* Unread badge */}
            {lead.unread_count > 0 && (
              <span className="ml-auto bg-[#1A56DB] text-white text-[10px] font-bold rounded-full h-4 min-w-[1rem] flex items-center justify-center px-1">
                {lead.unread_count}
              </span>
            )}
          </div>
        </div>
      </div>
    </button>
  )
}

// ── MessageBubble ─────────────────────────────────────────────────────────────

function MessageBubble({ msg, animate }: { msg: ChatMessage; animate?: boolean }) {
  const isOut = msg.direction === 'out'
  const isAI = isOut && msg.ai_response_used !== false

  return (
    <div
      className={cn(
        'flex mb-4 items-end gap-2',
        isOut ? 'justify-end' : 'justify-start',
        animate && 'animate-fade-in-up',
      )}
    >
      {/* Inbound avatar */}
      {!isOut && (
        <div className="h-7 w-7 rounded-full bg-[#E2EAF4] flex items-center justify-center shrink-0">
          <Phone size={12} className="text-[#6B7280]" />
        </div>
      )}

      <div className={cn('max-w-[68%]', isOut && 'items-end flex flex-col')}>
        {/* Sender label */}
        {isOut && (
          <div className="flex items-center gap-1 mb-1 justify-end">
            {isAI
              ? <><Sparkles size={10} className="text-[#1A56DB]" /><span className="text-[10px] text-[#6B7280]">Sofía</span></>
              : <><UserCheck size={10} className="text-[#0F172A]" /><span className="text-[10px] text-[#374151] font-medium">Agente</span></>
            }
          </div>
        )}

        {/* Bubble */}
        <div
          className={cn(
            'px-4 py-2.5 text-sm leading-relaxed',
            isOut
              ? isAI
                ? 'bg-[#1A56DB] text-white rounded-2xl rounded-br-sm shadow-sm shadow-blue-200'
                : 'bg-[#0F172A] text-white rounded-2xl rounded-br-sm'
              : 'bg-white text-[#111827] rounded-2xl rounded-bl-sm border border-[#E2EAF4] shadow-sm',
          )}
        >
          {msg.message_text}
        </div>

        {/* Timestamp */}
        {msg.created_at && (
          <span className={cn('text-[10px] text-[#C4CDD8] mt-1', isOut ? 'text-right' : 'text-left')}>
            {new Date(msg.created_at).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>

      {/* Outbound avatar */}
      {isOut && (
        <div
          className={cn(
            'h-7 w-7 rounded-full flex items-center justify-center shrink-0',
            isAI ? 'bg-[#DBEAFE]' : 'bg-[#0F172A]',
          )}
        >
          {isAI
            ? <Sparkles size={11} className="text-[#1A56DB]" />
            : <User size={11} className="text-white" />
          }
        </div>
      )}
    </div>
  )
}

// ── ConversationDetail ────────────────────────────────────────────────────────

function ConversationDetail({
  lead,
  onModeChange,
  onBack,
}: {
  lead: ConversationLead
  onModeChange: () => void
  onBack?: () => void
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [improving, setImproving] = useState(false)
  const [stage, setStage] = useState(lead.pipeline_stage ?? 'entrada')
  const [stageChanging, setStageChanging] = useState(false)
  const [toggling, setToggling] = useState(false)
  const [typing, setTyping] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const typingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const scrollRef = useRef<HTMLDivElement>(null)

  const isNearBottom = () => {
    const el = scrollRef.current
    if (!el) return true
    return el.scrollHeight - el.scrollTop - el.clientHeight < 120
  }

  const scrollToBottom = (force = false) => {
    if (force || isNearBottom()) {
      // Use two timeouts: immediate + delayed to handle both fast and slow renders
      bottomRef.current?.scrollIntoView({ behavior: 'auto' })
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100)
    }
  }

  const loadMessages = useCallback(async (opts?: { force?: boolean }) => {
    try {
      const msgs = await chatService.getMessages(lead.id, 500)
      setMessages((prev) => {
        // Only update if there are new messages to avoid unnecessary re-renders
        if (prev.length === msgs.length && prev[prev.length - 1]?.id === msgs[msgs.length - 1]?.id) return prev
        return msgs
      })
      // Scroll after state update — React will batch and update DOM first
      scrollToBottom(opts?.force)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [lead.id]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setLoading(true)
    setStage(lead.pipeline_stage ?? 'entrada')
    loadMessages({ force: true })
  }, [lead.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Polling fallback every 5s in case WebSocket misses an event
  useEffect(() => {
    const interval = setInterval(() => loadMessages(), 5000)
    return () => clearInterval(interval)
  }, [loadMessages])

  // Real-time WebSocket: receive inbound messages and typing indicator
  useWebSocketEvent(useCallback((event) => {
      const leadId = (event.data as any)?.lead_id
      if (leadId !== lead.id) return

      if (event.type === 'new_message' || event.type === 'human_mode_incoming') {
        loadMessages()
      } else if (event.type === 'typing') {
        if (lead.human_mode) return // suppress typing indicator during human mode
        setTyping(true)
        typingTimerRef.current && clearTimeout(typingTimerRef.current)
        typingTimerRef.current = setTimeout(() => setTyping(false), 4000)
      }
    }, [lead.id, lead.human_mode, loadMessages]))

  useEffect(() => () => { typingTimerRef.current && clearTimeout(typingTimerRef.current) }, [])

  async function handleSend() {
    if (!text.trim() || sending) return
    setSending(true)
    try {
      await conversationService.sendMessage(lead.id, text.trim())
      setText('')
      await loadMessages({ force: true })
    } catch (e) {
      console.error(e)
    } finally {
      setSending(false)
    }
  }

  async function handleImprove() {
    if (!text.trim() || improving) return
    setImproving(true)
    try {
      const improved = await conversationService.improveMessage(text.trim())
      setText(improved)
    } catch (e) {
      console.error(e)
      toast.error('No se pudo mejorar el mensaje')
    } finally {
      setImproving(false)
    }
  }

  async function handleToggleMode() {
    setToggling(true)
    try {
      if (lead.human_mode) {
        await conversationService.release(lead.id)
      } else {
        await conversationService.takeover(lead.id)
      }
      onModeChange()
    } catch (e) {
      console.error(e)
    } finally {
      setToggling(false)
    }
  }

  async function handleStageChange(newStage: string) {
    if (newStage === stage || stageChanging) return
    setStageChanging(true)
    try {
      await pipelineService.moveLeadToStage(lead.id, newStage)
      setStage(newStage)
    } catch (e) {
      console.error(e)
    } finally {
      setStageChanging(false)
    }
  }

  const currentStage = STAGES.find((s) => s.value === stage)
  const ch = lead.channel ? (CHANNEL_CFG[lead.channel] ?? { label: lead.channel, dot: '#9CA3AF' }) : null

  return (
    <div className="flex flex-col h-full bg-[#F7F9FC]">
      {/* ── Header ── */}
      <div className="px-3 sm:px-5 py-3 bg-white border-b border-[#EEF2F7] flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          {/* Back button — mobile only */}
          {onBack && (
            <button
              onClick={onBack}
              className="sm:hidden shrink-0 h-8 w-8 rounded-lg flex items-center justify-center text-[#6B7280] hover:bg-[#F0F4F8] transition-colors"
            >
              <ArrowLeft size={18} />
            </button>
          )}
          <div className={cn(
            'h-10 w-10 rounded-full flex items-center justify-center font-bold text-sm shrink-0',
            lead.human_mode ? 'bg-[#DBEAFE] text-[#1D4ED8]' : 'bg-gradient-to-br from-[#E2EAF4] to-[#C7D7EC] text-[#374151]',
          )}>
            {initials(lead.name, lead.phone)}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="font-semibold text-[#111827] truncate">{lead.name ?? 'Sin nombre'}</p>
              {ch && (
                <span className="flex items-center gap-1 text-[11px] text-[#6B7280]">
                  <span className="h-1.5 w-1.5 rounded-full inline-block" style={{ background: ch.dot }} />
                  {ch.label}
                </span>
              )}
            </div>
            <p className="text-xs text-[#9CA3AF] font-mono">{lead.phone}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Stage selector */}
          <div className="relative">
            <select
              value={stage}
              onChange={(e) => handleStageChange(e.target.value)}
              disabled={stageChanging}
              className={cn(
                'text-xs font-medium border rounded-lg pl-2.5 pr-7 py-1.5',
                'appearance-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-[#1A56DB]',
                'transition-colors duration-150',
              )}
              style={{
                borderColor: currentStage?.color + '60',
                background: currentStage?.color + '12',
                color: currentStage?.color,
              }}
            >
              {STAGES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
            <ChevronDown size={11} className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: currentStage?.color }} />
          </div>

          {/* Mode toggle */}
          <button
            onClick={handleToggleMode}
            disabled={toggling}
            className={cn(
              'flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-lg border transition-all duration-200',
              lead.human_mode
                ? 'bg-white border-[#D1D9E6] text-[#6B7280] hover:border-[#94A3B8]'
                : 'bg-[#1A56DB] border-[#1A56DB] text-white hover:bg-[#1740B0] shadow-sm shadow-blue-200',
              toggling && 'opacity-60 cursor-not-allowed',
            )}
          >
            {lead.human_mode
              ? <><Bot size={13} /><span className="hidden sm:inline">Liberar a IA</span></>
              : <><UserCheck size={13} /><span className="hidden sm:inline">Tomar control</span></>
            }
          </button>

          <button
            onClick={loadMessages}
            className="h-8 w-8 rounded-lg flex items-center justify-center text-[#9CA3AF] hover:text-[#374151] hover:bg-[#F0F4F8] transition-colors"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* ── Human mode banner ── */}
      {lead.human_mode && (
        <div className="px-5 py-2 bg-[#EBF5FF] border-b border-[#BFDBFE] flex items-center gap-2 shrink-0">
          <div className="h-1.5 w-1.5 rounded-full bg-[#1A56DB] animate-pulse" />
          <p className="text-xs text-[#1D4ED8] font-medium">
            Modo humano activo — Sofía no responderá hasta que liberes el control
          </p>
        </div>
      )}

      {/* ── Messages area ── */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-5">
        {loading ? (
          <div className="flex items-center justify-center h-40 text-[#9CA3AF] text-sm gap-2">
            <RefreshCw size={15} className="animate-spin" />
            <span>Cargando mensajes…</span>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-[#9CA3AF]">
            <div className="h-12 w-12 rounded-full bg-[#EEF2F7] flex items-center justify-center mb-3">
              <MessageSquare size={22} className="opacity-40" />
            </div>
            <p className="text-sm font-medium text-[#374151]">Sin mensajes todavía</p>
            <p className="text-xs text-[#9CA3AF] mt-1">El historial aparecerá aquí</p>
          </div>
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} msg={msg} />)
        )}
        {typing && (
          <div className="flex items-center gap-2 mb-4">
            <div className="h-7 w-7 rounded-full bg-[#DBEAFE] flex items-center justify-center shrink-0">
              <Sparkles size={11} className="text-[#1A56DB]" />
            </div>
            <div className="bg-white border border-[#E2EAF4] rounded-2xl rounded-bl-sm px-4 py-2.5 shadow-sm flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-[#94A3B8] animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="h-1.5 w-1.5 rounded-full bg-[#94A3B8] animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="h-1.5 w-1.5 rounded-full bg-[#94A3B8] animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* ── Input area ── */}
      <div className="px-4 py-3 bg-white border-t border-[#EEF2F7] shrink-0">
        {lead.human_mode ? (
          <div className="flex items-center gap-2">
            <div className="flex-1 relative">
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
                }}
                placeholder="Escribe un mensaje al cliente…"
                rows={2}
                className={cn(
                  'w-full resize-none rounded-xl border border-[#D1D9E6] px-3.5 py-2.5 text-sm',
                  'focus:outline-none focus:ring-2 focus:ring-[#1A56DB] focus:border-transparent',
                  'placeholder:text-[#C4CDD8] leading-relaxed transition-shadow',
                  improving && 'opacity-60',
                )}
              />
              <div className="absolute right-3 bottom-2 flex items-center gap-2">
                {text.trim() && (
                  <button
                    type="button"
                    onClick={handleImprove}
                    disabled={improving || sending}
                    title="Mejorar redacción con IA"
                    className={cn(
                      'flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-md transition-all',
                      improving
                        ? 'text-[#A78BFA] bg-[#F5F3FF] cursor-not-allowed'
                        : 'text-[#7C3AED] bg-[#F5F3FF] hover:bg-[#EDE9FE]',
                    )}
                  >
                    <Wand2 size={11} className={improving ? 'animate-pulse' : ''} />
                    {improving ? 'Mejorando…' : 'Mejorar'}
                  </button>
                )}
                <span className="text-[10px] text-[#C4CDD8]">↵ enviar</span>
              </div>
            </div>
            <button
              onClick={handleSend}
              disabled={!text.trim() || sending || improving}
              className={cn(
                'h-[52px] w-12 rounded-xl flex items-center justify-center transition-all duration-200 shrink-0',
                text.trim() && !sending && !improving
                  ? 'bg-[#1A56DB] shadow-sm shadow-blue-200 hover:bg-[#1740B0]'
                  : 'bg-[#E2EAF4] cursor-not-allowed',
              )}
            >
              {sending
                ? <RefreshCw size={16} className="animate-spin text-white" />
                : <Send size={16} className={text.trim() && !improving ? 'text-white' : 'text-[#9CA3AF]'} />
              }
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-3 px-1 py-1">
            <div className="h-8 w-8 rounded-full bg-[#F0F4F8] flex items-center justify-center shrink-0">
              <WifiOff size={14} className="text-[#9CA3AF]" />
            </div>
            <div className="flex-1">
              <p className="text-xs text-[#374151] font-medium">Sofía está a cargo</p>
              <p className="text-[11px] text-[#9CA3AF]">Toma el control para responder manualmente</p>
            </div>
            <button
              onClick={handleToggleMode}
              disabled={toggling}
              className="flex items-center gap-1 text-xs font-semibold text-[#1A56DB] hover:text-[#1740B0] transition-colors"
            >
              Tomar <ArrowRight size={12} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export function ConversationsPage() {
  const [leads, setLeads] = useState<ConversationLead[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [modeFilter, setModeFilter] = useState<'all' | 'human' | 'ai'>('all')
  const [selectedId, setSelectedId] = useState<number | null>(() => {
    const params = new URLSearchParams(window.location.search)
    const leadId = params.get('lead_id')
    return leadId ? parseInt(leadId, 10) : null
  })
  const [selectedLead, setSelectedLead] = useState<ConversationLead | null>(null)
  const [mobileShowDetail, setMobileShowDetail] = useState(false)

  const load = useCallback(async () => {
    setLoadError(null)
    try {
      const data = await conversationService.list(
        modeFilter === 'all' ? undefined : (modeFilter as 'human' | 'ai'),
        search || undefined,
      )
      setLeads(data)
      if (data.length > 0 && !selectedId) setSelectedId(data[0].id)
    } catch (e) {
      console.error(e)
      setLoadError('No se pudieron cargar las conversaciones.')
    } finally {
      setLoading(false)
    }
  }, [modeFilter, search, selectedId])

  useEffect(() => { load() }, [modeFilter])

  useEffect(() => {
    const t = setTimeout(() => load(), 350)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    const found = leads.find((l) => l.id === selectedId) ?? null
    setSelectedLead(found)
  }, [selectedId, leads])

  // Real-time WebSocket: refresh lead list on new messages or mode changes
  useWebSocketEvent(useCallback((event) => {
      if (
        event.type === 'new_message' ||
        event.type === 'human_mode_incoming' ||
        event.type === 'human_mode_changed' ||
        event.type === 'lead_frustrated'
      ) {
        load()
      }
    }, [load]))

  const humanCount = leads.filter((l) => l.human_mode).length
  const totalUnread = leads.reduce((a, l) => a + l.unread_count, 0)

  const FILTERS = [
    { id: 'all'   as const, label: 'Todos',   count: leads.length },
    { id: 'human' as const, label: 'Humano',  count: humanCount },
    { id: 'ai'    as const, label: 'IA',       count: leads.length - humanCount },
  ]

  return (
    <div className="flex overflow-hidden bg-[#F0F4F8]" style={{ height: 'calc(100vh - 56px)' }}>

      {/* ═══ Left sidebar ═══ */}
      <div className={cn(
        'shrink-0 flex flex-col bg-white border-r border-[#EEF2F7] shadow-sm',
        'w-full sm:w-[300px]',
        mobileShowDetail ? 'hidden sm:flex' : 'flex',
      )}>

        {/* Sidebar header */}
        <div className="px-4 pt-4 pb-3 border-b border-[#EEF2F7]">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="h-7 w-7 rounded-lg bg-[#1A56DB] flex items-center justify-center">
                <Inbox size={14} className="text-white" />
              </div>
              <h1 className="font-bold text-[#111827] text-sm tracking-tight">Conversaciones</h1>
            </div>
            <div className="flex items-center gap-1">
              {totalUnread > 0 && (
                <span className="bg-[#1A56DB] text-white text-[10px] font-bold rounded-full px-1.5 py-0.5 leading-none">
                  {totalUnread}
                </span>
              )}
              <button
                onClick={load}
                className="h-7 w-7 rounded-lg flex items-center justify-center text-[#9CA3AF] hover:text-[#374151] hover:bg-[#F0F4F8] transition-colors"
              >
                <RefreshCw size={13} />
              </button>
            </div>
          </div>

          {/* Search */}
          <div className="relative mb-3">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#C4CDD8] pointer-events-none" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar nombre o teléfono…"
              className={cn(
                'w-full h-8 pl-8 pr-3 text-xs rounded-lg border border-[#D1D9E6]',
                'focus:outline-none focus:ring-2 focus:ring-[#1A56DB] focus:border-transparent',
                'bg-[#F7F9FC] placeholder:text-[#C4CDD8] transition-shadow',
              )}
            />
          </div>

          {/* Filter tabs */}
          <div className="flex gap-1 bg-[#F0F4F8] rounded-lg p-0.5">
            {FILTERS.map(({ id, label, count }) => (
              <button
                key={id}
                onClick={() => setModeFilter(id)}
                className={cn(
                  'flex-1 py-1 text-[11px] font-semibold rounded-md transition-all duration-150',
                  modeFilter === id
                    ? 'bg-white text-[#1A56DB] shadow-sm'
                    : 'text-[#6B7280] hover:text-[#374151]',
                )}
              >
                {label}
                <span className={cn('ml-1', modeFilter === id ? 'text-[#1A56DB]' : 'text-[#9CA3AF]')}>
                  {count}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Lead list */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-48 text-[#9CA3AF] gap-2">
              <RefreshCw size={18} className="animate-spin" />
              <span className="text-xs">Cargando…</span>
            </div>
          ) : loadError ? (
            <div className="flex flex-col items-center justify-center h-48 text-[#9CA3AF] px-6 text-center">
              <div className="h-12 w-12 rounded-full bg-red-50 flex items-center justify-center mb-3">
                <AlertTriangle size={20} className="text-red-400" />
              </div>
              <p className="text-xs font-medium text-[#374151]">{loadError}</p>
              <button onClick={load} className="mt-2 text-[11px] text-[#1A56DB] hover:underline">Reintentar</button>
            </div>
          ) : leads.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-[#9CA3AF] px-6 text-center">
              <div className="h-12 w-12 rounded-full bg-[#F0F4F8] flex items-center justify-center mb-3">
                <MessageSquare size={20} className="opacity-40" />
              </div>
              <p className="text-xs font-medium text-[#374151]">Sin conversaciones</p>
              <p className="text-[11px] text-[#9CA3AF] mt-1">
                {search ? 'Intenta con otro término' : 'Los leads aparecerán aquí'}
              </p>
            </div>
          ) : (
            leads.map((lead) => (
              <ConversationItem
                key={lead.id}
                lead={lead}
                selected={lead.id === selectedId}
                onClick={() => { setSelectedId(lead.id); setMobileShowDetail(true) }}
              />
            ))
          )}
        </div>
      </div>

      {/* ═══ Right panel ═══ */}
      <div className={cn(
        'flex-1 flex flex-col overflow-hidden',
        mobileShowDetail ? 'flex' : 'hidden sm:flex',
      )}>
        {selectedLead ? (
          <ConversationDetail
            key={selectedLead.id}
            lead={selectedLead}
            onModeChange={load}
            onBack={() => setMobileShowDetail(false)}
          />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-[#9CA3AF]">
            <div className="h-20 w-20 rounded-2xl bg-white border border-[#EEF2F7] shadow-sm flex items-center justify-center mb-4">
              <Inbox size={36} className="text-[#D1D9E6]" />
            </div>
            <p className="text-base font-semibold text-[#374151]">Selecciona una conversación</p>
            <p className="text-sm text-[#9CA3AF] mt-1">
              Elige un lead de la lista para ver el historial
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
