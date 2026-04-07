import { useEffect, useRef, useState } from 'react'
import { Search, Bot, User, UserCheck, Zap, GitBranch, Wrench, TrendingUp, AlertTriangle, PhoneCall, PhoneOff, AlertCircle, ChevronDown, ChevronRight, ArrowRight, Download } from 'lucide-react'
import { useObservabilityStore } from '../store/observabilityStore'
import type { ConversationSearchItem, TimelineEvent, ChatMessage } from '../types/observability.types'

type TimelineFilter = 'all' | 'llm_call' | 'handoff' | 'error' | 'score_change'

const FILTER_LABELS: Record<TimelineFilter, string> = {
  all: 'Todo',
  llm_call: 'LLM',
  handoff: 'Handoffs',
  error: 'Errores',
  score_change: 'Score',
}

function matchesFilter(ev: TimelineEvent, filter: TimelineFilter): boolean {
  if (filter === 'all') return true
  if (filter === 'score_change') return ev.type === 'score_change' || ev.type === 'pipeline_stage'
  return ev.type === filter
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtTime(ts: string | null | undefined) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function fmtMs(ms: number | undefined) {
  if (ms == null) return null
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}

function agentLabel(a: string | undefined) {
  if (!a) return '—'
  const map: Record<string, string> = {
    qualifier: 'Qualifier',
    scheduler: 'Scheduler',
    follow_up: 'Follow-up',
    property: 'Property',
    supervisor: 'Supervisor',
  }
  return map[a] || a
}

function channelLabel(c: string) {
  const map: Record<string, string> = { whatsapp: 'WhatsApp', telegram: 'Telegram', webchat: 'Web Chat', instagram: 'Instagram' }
  return map[c] || c
}

const AGENT_COLOR: Record<string, string> = {
  qualifier: 'bg-blue-100 text-blue-700',
  scheduler: 'bg-violet-100 text-violet-700',
  follow_up: 'bg-emerald-100 text-emerald-700',
  property: 'bg-amber-100 text-amber-700',
  supervisor: 'bg-slate-100 text-slate-700',
}

// ── Chat bubble ───────────────────────────────────────────────────────────────

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const isInbound = msg.direction === 'inbound'
  const isHuman = msg.sender_type === 'human_agent'

  return (
    <div className={`flex gap-2 ${isInbound ? 'justify-start' : 'justify-end'}`}>
      {isInbound && (
        <div className="w-7 h-7 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0 mt-1">
          <User size={14} className="text-slate-500" />
        </div>
      )}
      <div className={`max-w-[75%] ${isInbound ? '' : 'items-end'} flex flex-col gap-0.5`}>
        <div
          className={`rounded-2xl px-3 py-2 text-sm leading-snug ${
            isInbound
              ? 'bg-white border border-slate-200 text-slate-800 rounded-tl-sm'
              : isHuman
              ? 'bg-amber-500 text-white rounded-tr-sm'
              : 'bg-blue-600 text-white rounded-tr-sm'
          }`}
        >
          {msg.content}
        </div>
        <span className="text-[10px] text-slate-400 px-1">{fmtTime(msg.timestamp)}</span>
      </div>
      {!isInbound && (
        <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-1 ${isHuman ? 'bg-amber-100' : 'bg-blue-100'}`}>
          {isHuman ? <UserCheck size={14} className="text-amber-600" /> : <Bot size={14} className="text-blue-600" />}
        </div>
      )}
    </div>
  )
}

// ── Timeline event row ────────────────────────────────────────────────────────

function TimelineRow({ ev }: { ev: TimelineEvent }) {
  const [expanded, setExpanded] = useState(false)

  const canExpand = ev.type === 'llm_call' || ev.type === 'tool' || ev.type === 'score_change' || ev.type === 'error' || ev.type === 'sentiment' || ev.type === 'handoff'

  const icon = {
    agent_selected: <Zap size={12} className="text-blue-500" />,
    llm_call: <Bot size={12} className="text-purple-500" />,
    handoff: <GitBranch size={12} className="text-orange-500" />,
    tool: <Wrench size={12} className="text-green-600" />,
    pipeline_stage: <ArrowRight size={12} className="text-slate-500" />,
    score_change: <TrendingUp size={12} className="text-cyan-500" />,
    sentiment: <span className="text-xs">💬</span>,
    escalation: <AlertTriangle size={12} className="text-red-500" />,
    human_takeover: <PhoneCall size={12} className="text-amber-500" />,
    human_release: <PhoneOff size={12} className="text-emerald-500" />,
    error: <AlertCircle size={12} className="text-red-500" />,
    fallback: <AlertTriangle size={12} className="text-yellow-500" />,
  }[ev.type] ?? <span className="w-3 h-3 rounded-full bg-slate-300 inline-block" />

  function renderSummary() {
    switch (ev.type) {
      case 'agent_selected':
        return (
          <span>
            agent:{' '}
            <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-semibold ${AGENT_COLOR[ev.agent || ''] || 'bg-slate-100 text-slate-700'}`}>
              {agentLabel(ev.agent)}
            </span>
          </span>
        )
      case 'llm_call':
        return (
          <span className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-purple-700">{ev.provider}/{ev.model}</span>
            {ev.input_tokens != null && <span className="text-slate-500">{ev.input_tokens}in / {ev.output_tokens}out tokens</span>}
            {ev.latency_ms != null && <span className="text-slate-500">{fmtMs(ev.latency_ms)}</span>}
            {ev.cost_usd != null && <span className="text-slate-500">${ev.cost_usd.toFixed(5)}</span>}
          </span>
        )
      case 'handoff':
        return (
          <span>
            <span className={`inline-flex items-center px-1 py-0.5 rounded text-[11px] font-semibold ${AGENT_COLOR[ev.from_agent || ''] || 'bg-slate-100 text-slate-600'}`}>
              {agentLabel(ev.from_agent)}
            </span>
            <ArrowRight size={10} className="inline mx-1 text-slate-400" />
            <span className={`inline-flex items-center px-1 py-0.5 rounded text-[11px] font-semibold ${AGENT_COLOR[ev.to_agent || ''] || 'bg-slate-100 text-slate-600'}`}>
              {agentLabel(ev.to_agent)}
            </span>
            {ev.reason && <span className="text-slate-500 ml-1">· {ev.reason}</span>}
          </span>
        )
      case 'tool':
        return <span className="font-mono text-green-700">{ev.tool_name}{ev.success === false ? ' ✗' : ' ✓'}</span>
      case 'pipeline_stage':
        return (
          <span>
            {ev.stage_before && <span className="text-slate-500">{ev.stage_before}</span>}
            <ArrowRight size={10} className="inline mx-1 text-slate-400" />
            <span className="font-semibold text-slate-800">{ev.stage_after}</span>
            {ev.score_before != null && ev.score_after != null && (
              <span className="text-slate-500 ml-1">· score {ev.score_before}→{ev.score_after}</span>
            )}
          </span>
        )
      case 'score_change':
        return (
          <span>
            score{' '}
            <span className="font-semibold">{ev.score_before ?? '?'}→{ev.score_after ?? '?'}</span>
            {ev.score_delta != null && (
              <span className={`ml-1 font-semibold ${(ev.score_delta ?? 0) >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                {(ev.score_delta ?? 0) >= 0 ? '+' : ''}{ev.score_delta}
              </span>
            )}
          </span>
        )
      case 'sentiment': {
        const s = ev.score ?? 0
        const color = s >= 0.7 ? 'text-red-600' : s >= 0.4 ? 'text-amber-500' : 'text-emerald-600'
        const emoji = s >= 0.7 ? '🔴' : s >= 0.4 ? '🟡' : '🟢'
        return (
          <span>
            sentiment:{' '}
            <span className={`font-semibold ${color}`}>{s.toFixed(2)} {emoji}</span>
            {ev.emotions && ev.emotions.length > 0 && (
              <span className="text-slate-500 ml-1">· {ev.emotions.join(', ')}</span>
            )}
          </span>
        )
      }
      case 'escalation':
        return (
          <span className="font-semibold text-red-600">
            ESCALATION TRIGGERED
            {ev.reason && <span className="font-normal text-slate-600 ml-1">· reason: {ev.reason}</span>}
            {ev.frustration_score != null && <span className="font-normal text-slate-600 ml-1">· frustration: {ev.frustration_score.toFixed(2)}</span>}
          </span>
        )
      case 'human_takeover':
        return (
          <span>
            human_mode = <span className="font-semibold text-amber-600">true</span>
            {ev.agent_name && <span className="text-slate-500 ml-1">· taken by {ev.agent_name}</span>}
          </span>
        )
      case 'human_release':
        return (
          <span>
            human_mode = <span className="font-semibold text-emerald-600">false</span>
            {ev.note && <span className="text-slate-500 ml-1">· "{ev.note}"</span>}
          </span>
        )
      case 'error':
        return <span className="text-red-600">{ev.error_type}: {ev.error_message}</span>
      case 'fallback':
        return <span className="text-yellow-700">fallback → {ev.provider}{ev.reason ? ` · ${ev.reason}` : ''}</span>
      default:
        return null
    }
  }

  function renderDetail() {
    switch (ev.type) {
      case 'llm_call': {
        const meta = (ev as unknown as { event_metadata?: Record<string, unknown> }).event_metadata
        const userMsgs = meta?.user_messages as Array<{role: string, content: string}> | undefined
        const ragChunks = meta?.rag_chunks_used as unknown[] | undefined
        const temp = meta?.temperature as number | undefined
        return (
          <div className="space-y-2 mt-2 pl-4 border-l-2 border-purple-200">
            {ev.prompt_hash && <p className="text-[10px] text-slate-400">prompt hash: <code className="font-mono">{ev.prompt_hash.slice(0, 16)}…</code></p>}
            {temp != null && <p className="text-[10px] text-slate-400">temperature: {temp}</p>}
            {userMsgs && userMsgs.length > 0 && (
              <div>
                <p className="text-[10px] font-semibold text-slate-500 mb-1">Mensajes enviados al LLM:</p>
                <div className="space-y-1 max-h-40 overflow-auto">
                  {userMsgs.map((m, i) => (
                    <div key={i} className={`text-[10px] rounded px-2 py-1 ${m.role === 'user' ? 'bg-blue-50 text-blue-800' : 'bg-slate-50 text-slate-700'}`}>
                      <span className="font-semibold uppercase">{m.role}: </span>{m.content}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {ragChunks && ragChunks.length > 0 && (
              <p className="text-[10px] text-slate-500">RAG chunks: {JSON.stringify(ragChunks)}</p>
            )}
            {ev.completion_snippet && (
              <div>
                <p className="text-[10px] font-semibold text-slate-500 mb-1">Respuesta:</p>
                <pre className="text-xs text-slate-700 bg-white border border-slate-200 rounded p-2 whitespace-pre-wrap max-h-32 overflow-auto">
                  {ev.completion_snippet}
                </pre>
              </div>
            )}
          </div>
        )
      }
      case 'tool':
        return (
          <div className="space-y-1 mt-2 pl-4 border-l-2 border-green-200">
            {ev.tool_input && <pre className="text-xs bg-white border border-slate-200 rounded p-2 overflow-auto max-h-24">{JSON.stringify(ev.tool_input, null, 2)}</pre>}
            {ev.tool_output !== undefined && <pre className="text-xs bg-white border border-slate-200 rounded p-2 overflow-auto max-h-24">{JSON.stringify(ev.tool_output, null, 2)}</pre>}
          </div>
        )
      case 'score_change':
        return ev.extracted_fields && Object.keys(ev.extracted_fields).length > 0 ? (
          <div className="mt-2 pl-4 border-l-2 border-cyan-200">
            <p className="text-xs text-slate-500 mb-1">extracted:</p>
            <pre className="text-xs bg-white border border-slate-200 rounded p-2 overflow-auto max-h-24">{JSON.stringify(ev.extracted_fields, null, 2)}</pre>
          </div>
        ) : null
      case 'sentiment': {
        const meta = (ev as unknown as { event_metadata?: Record<string, unknown> }).event_metadata
        const keywords = meta?.keywords_matched as string[] | undefined
        const actionLevel = meta?.action_level as string | undefined
        return (ev.emotions && ev.emotions.length > 0) || keywords?.length || actionLevel ? (
          <div className="mt-2 pl-4 border-l-2 border-yellow-200 space-y-1">
            {actionLevel && <p className="text-[10px] text-slate-500">action_level: <span className="font-semibold">{actionLevel}</span></p>}
            {ev.emotions && ev.emotions.length > 0 && (
              <p className="text-[10px] text-slate-500">emotions: {ev.emotions.join(', ')}</p>
            )}
            {keywords && keywords.length > 0 && (
              <p className="text-[10px] text-slate-500">keywords: {keywords.join(', ')}</p>
            )}
          </div>
        ) : null
      }
      case 'handoff':
        return ev.reason ? (
          <div className="mt-2 pl-4 border-l-2 border-orange-200">
            <p className="text-[10px] text-slate-500">reason: {ev.reason}</p>
          </div>
        ) : null
      case 'error':
        return null
      default:
        return null
    }
  }

  const detail = renderDetail()

  return (
    <div
      className={`flex gap-2 py-1 px-2 rounded hover:bg-slate-50 transition-colors ${canExpand ? 'cursor-pointer' : ''}`}
      onClick={() => canExpand && setExpanded(e => !e)}
    >
      <span className="text-[10px] text-slate-400 font-mono w-20 flex-shrink-0 pt-0.5">{fmtTime(ev.timestamp)}</span>
      <span className="flex-shrink-0 pt-0.5">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1">
          <span className="text-xs text-slate-700 flex-1 min-w-0">{renderSummary()}</span>
          {canExpand && detail && (
            <span className="text-slate-400 flex-shrink-0">
              {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </span>
          )}
        </div>
        {expanded && detail}
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export function ConversationDebugger() {
  const {
    conversations,
    isLoadingConversations,
    selectedTrace,
    isLoadingTrace,
    traceError,
    searchConversations,
    fetchTrace,
    clearTrace,
  } = useObservabilityStore()

  const [query, setQuery] = useState('')
  const [selectedLeadId, setSelectedLeadId] = useState<number | null>(null)
  const [timelineFilter, setTimelineFilter] = useState<TimelineFilter>('all')
  const chatBottomRef = useRef<HTMLDivElement>(null)

  function handleExport() {
    if (!selectedTrace) return
    const blob = new Blob([JSON.stringify(selectedTrace, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `trace-lead-${selectedTrace.lead_id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  useEffect(() => { searchConversations() }, [searchConversations])

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [selectedTrace?.messages])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    searchConversations(query || undefined)
  }

  const handleSelect = (conv: ConversationSearchItem) => {
    setSelectedLeadId(conv.lead_id)
    fetchTrace(conv.lead_id)
  }

  return (
    <div className="flex gap-4 h-[80vh] min-h-[540px]">

      {/* ── Conversation list ── */}
      <div className="w-64 flex-shrink-0 flex flex-col gap-2">
        <form onSubmit={handleSearch} className="flex gap-1">
          <div className="relative flex-1">
            <Search size={13} className="absolute left-2 top-2.5 text-slate-400" />
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Buscar lead…"
              className="w-full pl-7 pr-2 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button type="submit" className="px-2.5 py-2 bg-slate-900 text-white text-xs rounded-lg hover:bg-slate-700 transition-colors">
            Buscar
          </button>
        </form>

        <div className="flex-1 overflow-y-auto space-y-1">
          {isLoadingConversations
            ? Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 animate-pulse rounded-lg" />)
            : conversations.length === 0
            ? <p className="text-xs text-slate-400 text-center py-8">Sin resultados</p>
            : conversations.map(conv => (
              <button
                key={conv.lead_id}
                onClick={() => handleSelect(conv)}
                className={`w-full text-left rounded-lg border p-2.5 transition-colors ${
                  selectedLeadId === conv.lead_id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-slate-200 bg-white hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-xs font-medium text-slate-900 truncate">{conv.lead_name}</span>
                  {conv.human_mode && (
                    <span className="text-[10px] bg-amber-100 text-amber-700 px-1 py-0.5 rounded-full flex-shrink-0 ml-1">
                      humano
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-500 truncate">{conv.last_message}</p>
                <div className="flex gap-1.5 mt-1">
                  <span className="text-[10px] text-slate-400">{conv.current_stage}</span>
                  <span className="text-[10px] text-slate-300">·</span>
                  <span className="text-[10px] text-slate-400">{conv.total_messages} msgs</span>
                </div>
              </button>
            ))
          }
        </div>
      </div>

      {/* ── Debugger panel ── */}
      <div className="flex-1 flex flex-col gap-2 min-w-0">
        {!selectedLeadId ? (
          <div className="flex-1 rounded-xl border border-slate-200 flex items-center justify-center">
            <p className="text-sm text-slate-400">Selecciona una conversación para ver el debugger</p>
          </div>
        ) : isLoadingTrace ? (
          <div className="flex-1 space-y-2">
            {Array.from({ length: 3 }).map((_, i) => <div key={i} className="h-16 bg-slate-100 animate-pulse rounded-xl" />)}
          </div>
        ) : traceError ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {traceError}
            <button onClick={() => { clearTrace(); setSelectedLeadId(null) }} className="ml-3 text-red-500 underline">
              Cerrar
            </button>
          </div>
        ) : selectedTrace ? (
          <>
            {/* Header */}
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">{selectedTrace.summary.lead_name}</h3>
                  <p className="text-xs text-slate-500">
                    Canal: {channelLabel(selectedTrace.summary.channel)}
                    {' · '}Score: <span className="font-semibold text-slate-700">{selectedTrace.summary.lead_score}</span>
                    {' · '}Stage: <span className="font-semibold text-slate-700">{selectedTrace.summary.current_stage}</span>
                    {selectedTrace.summary.human_mode && (
                      <span className="ml-1 bg-amber-100 text-amber-700 text-[10px] px-1.5 py-0.5 rounded-full">modo humano</span>
                    )}
                  </p>
                </div>
                <p className="text-xs text-slate-400">
                  Inicio: {fmtTime(selectedTrace.summary.started_at)}
                </p>
              </div>
              <div className="grid grid-cols-4 gap-3 pt-2 border-t border-slate-100">
                {[
                  { label: 'Mensajes', value: selectedTrace.summary.total_messages },
                  { label: 'Tokens', value: selectedTrace.summary.total_tokens.toLocaleString() },
                  { label: 'Costo', value: `$${selectedTrace.summary.total_cost_usd.toFixed(4)}` },
                  { label: 'Agente', value: agentLabel(selectedTrace.summary.current_agent) },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <p className="text-[10px] text-slate-400 uppercase tracking-wide">{label}</p>
                    <p className="text-sm font-bold text-slate-800">{value}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Split view */}
            <div className="flex-1 flex gap-3 min-h-0">
              {/* Chat */}
              <div className="flex-1 flex flex-col rounded-xl border border-slate-200 bg-slate-50 overflow-hidden">
                <div className="px-3 py-2 border-b border-slate-200 bg-white">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Chat</p>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-3">
                  {selectedTrace.messages.map(msg => <ChatBubble key={msg.id} msg={msg} />)}
                  <div ref={chatBottomRef} />
                </div>
              </div>

              {/* Timeline */}
              <div className="w-[420px] flex-shrink-0 flex flex-col rounded-xl border border-slate-200 bg-white overflow-hidden">
                <div className="px-3 py-2 border-b border-slate-200 flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex-shrink-0">Timeline interno</p>
                  <button
                    onClick={handleExport}
                    title="Exportar como JSON"
                    className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 border border-slate-200 rounded px-1.5 py-0.5 hover:bg-slate-50 transition-colors"
                  >
                    <Download size={11} /> JSON
                  </button>
                </div>
                {/* Filter bar */}
                <div className="flex gap-1 px-2 py-1.5 border-b border-slate-100">
                  {(Object.keys(FILTER_LABELS) as TimelineFilter[]).map(f => (
                    <button
                      key={f}
                      onClick={() => setTimelineFilter(f)}
                      className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                        timelineFilter === f
                          ? 'bg-slate-800 text-white'
                          : 'text-slate-500 hover:bg-slate-100'
                      }`}
                    >
                      {FILTER_LABELS[f]}
                    </button>
                  ))}
                </div>
                <div className="flex-1 overflow-y-auto py-1">
                  {selectedTrace.timeline.filter(ev => matchesFilter(ev, timelineFilter)).length === 0 ? (
                    <p className="text-xs text-slate-400 text-center py-8">Sin eventos</p>
                  ) : (
                    selectedTrace.timeline
                      .filter(ev => matchesFilter(ev, timelineFilter))
                      .map(ev => <TimelineRow key={ev.id} ev={ev} />)
                  )}
                </div>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
