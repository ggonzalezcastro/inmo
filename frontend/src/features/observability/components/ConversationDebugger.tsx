import { useEffect, useState } from 'react'
import { Search, ChevronDown, ChevronRight } from 'lucide-react'
import { useObservabilityStore } from '../store/observabilityStore'
import type { TimelineItem, TimelineItemType } from '../types/observability.types'

const TYPE_COLORS: Record<TimelineItemType, string> = {
  message: 'bg-blue-500',
  llm_call: 'bg-purple-500',
  handoff: 'bg-orange-500',
  error: 'bg-red-500',
  tool: 'bg-green-500',
  pipeline_stage: 'bg-slate-400',
}

const TYPE_LABELS: Record<TimelineItemType, string> = {
  message: 'Mensaje',
  llm_call: 'LLM',
  handoff: 'Handoff',
  error: 'Error',
  tool: 'Tool',
  pipeline_stage: 'Pipeline',
}

const TYPE_BG: Record<TimelineItemType, string> = {
  message: 'border-blue-200 bg-blue-50',
  llm_call: 'border-purple-200 bg-purple-50',
  handoff: 'border-orange-200 bg-orange-50',
  error: 'border-red-200 bg-red-50',
  tool: 'border-green-200 bg-green-50',
  pipeline_stage: 'border-slate-200 bg-slate-50',
}

function TimelineDot({ type }: { type: TimelineItemType }) {
  return (
    <div
      className={`w-3 h-3 rounded-full flex-shrink-0 mt-1 ${TYPE_COLORS[type]}`}
    />
  )
}

function TraceItemRow({
  item,
  showPrompts,
}: {
  item: TimelineItem
  showPrompts: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const isExpandable = item.type === 'llm_call' || item.type === 'tool' || item.type === 'error'

  return (
    <div className={`rounded-lg border p-3 ${TYPE_BG[item.type]}`}>
      <div
        className="flex items-start gap-3 cursor-pointer"
        onClick={() => isExpandable && setExpanded((e) => !e)}
      >
        <TimelineDot type={item.type} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {TYPE_LABELS[item.type]}
            </span>
            <span className="text-xs text-slate-400">
              {new Date(item.timestamp).toLocaleTimeString('es-CL')}
            </span>
            {item.type === 'llm_call' && item.latency_ms != null && (
              <span className="text-xs text-slate-500">{item.latency_ms}ms</span>
            )}
            {item.type === 'llm_call' && item.total_tokens != null && (
              <span className="text-xs text-purple-600">{item.total_tokens} tokens</span>
            )}
            {item.type === 'llm_call' && item.cost_usd != null && (
              <span className="text-xs text-slate-500">${item.cost_usd.toFixed(5)}</span>
            )}
          </div>

          {/* Content preview */}
          {item.type === 'message' && item.content && (
            <p className="text-sm text-slate-700 line-clamp-2">
              <span className="font-medium">
                {item.direction === 'inbound' ? '→ ' : '← '}
              </span>
              {item.content}
            </p>
          )}
          {item.type === 'handoff' && (
            <p className="text-sm text-slate-700">
              <span className="font-medium">{item.from_agent}</span>
              {' → '}
              <span className="font-medium">{item.to_agent}</span>
              {item.reason && <span className="text-slate-500"> · {item.reason}</span>}
            </p>
          )}
          {item.type === 'pipeline_stage' && (
            <p className="text-sm text-slate-700">
              {item.previous_stage && (
                <span className="text-slate-500">{item.previous_stage} → </span>
              )}
              <span className="font-medium">{item.stage}</span>
            </p>
          )}
          {item.type === 'error' && (
            <p className="text-sm text-red-700">
              {item.error_type}: {item.error_message}
            </p>
          )}
          {item.type === 'tool' && (
            <p className="text-sm text-slate-700">
              <span className="font-medium">{item.tool_name}</span>
            </p>
          )}
          {item.type === 'llm_call' && item.model && (
            <p className="text-xs text-slate-500">{item.model}</p>
          )}
        </div>
        {isExpandable && (
          <div className="flex-shrink-0 text-slate-400">
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </div>
        )}
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="mt-3 pl-6 space-y-2 border-t border-slate-200 pt-3">
          {item.type === 'llm_call' && showPrompts && item.prompt && (
            <div>
              <p className="text-xs font-semibold text-slate-500 mb-1">Prompt</p>
              <pre className="text-xs text-slate-700 whitespace-pre-wrap bg-white rounded p-2 border border-slate-200 max-h-48 overflow-auto">
                {item.prompt}
              </pre>
            </div>
          )}
          {item.type === 'llm_call' && item.completion && (
            <div>
              <p className="text-xs font-semibold text-slate-500 mb-1">Respuesta</p>
              <pre className="text-xs text-slate-700 whitespace-pre-wrap bg-white rounded p-2 border border-slate-200 max-h-48 overflow-auto">
                {item.completion}
              </pre>
            </div>
          )}
          {item.type === 'tool' && item.tool_input && (
            <div>
              <p className="text-xs font-semibold text-slate-500 mb-1">Input</p>
              <pre className="text-xs text-slate-700 bg-white rounded p-2 border border-slate-200 overflow-auto max-h-32">
                {JSON.stringify(item.tool_input, null, 2)}
              </pre>
            </div>
          )}
          {item.type === 'tool' && item.tool_output !== undefined && (
            <div>
              <p className="text-xs font-semibold text-slate-500 mb-1">Output</p>
              <pre className="text-xs text-slate-700 bg-white rounded p-2 border border-slate-200 overflow-auto max-h-32">
                {JSON.stringify(item.tool_output, null, 2)}
              </pre>
            </div>
          )}
          {item.type === 'error' && item.error_message && (
            <pre className="text-xs text-red-700 bg-white rounded p-2 border border-red-200 overflow-auto max-h-32">
              {item.error_message}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

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
  const [showPrompts, setShowPrompts] = useState(false)

  useEffect(() => {
    searchConversations()
  }, [searchConversations])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    searchConversations(query || undefined)
  }

  const handleSelectLead = (leadId: number) => {
    setSelectedLeadId(leadId)
    fetchTrace(leadId)
  }

  return (
    <div className="flex gap-4 h-[75vh] min-h-[500px]">
      {/* Left panel — conversation list */}
      <div className="w-72 flex-shrink-0 flex flex-col gap-3">
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar lead..."
              className="w-full pl-8 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <button
            type="submit"
            className="px-3 py-2 bg-slate-900 text-white text-sm rounded-lg hover:bg-slate-700 transition-colors"
          >
            Buscar
          </button>
        </form>

        <div className="flex-1 overflow-y-auto space-y-1">
          {isLoadingConversations ? (
            Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-16 bg-slate-100 animate-pulse rounded-lg" />
            ))
          ) : conversations.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-8">Sin resultados</p>
          ) : (
            conversations.map((conv) => (
              <button
                key={conv.lead_id}
                onClick={() => handleSelectLead(conv.lead_id)}
                className={`w-full text-left rounded-lg border p-3 transition-colors ${
                  selectedLeadId === conv.lead_id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-slate-200 bg-white hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-sm font-medium text-slate-900 truncate">
                    {conv.lead_name}
                  </span>
                  {conv.human_mode && (
                    <span className="text-xs bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded-full">
                      humano
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-500 truncate">{conv.last_message}</p>
                <div className="flex gap-2 mt-1">
                  <span className="text-xs text-slate-400">{conv.current_stage}</span>
                  <span className="text-xs text-slate-300">·</span>
                  <span className="text-xs text-slate-400">{conv.total_messages} msgs</span>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Right panel — trace */}
      <div className="flex-1 flex flex-col gap-3 min-w-0">
        {!selectedLeadId ? (
          <div className="flex-1 rounded-xl border border-slate-200 flex items-center justify-center">
            <p className="text-sm text-slate-400">
              Selecciona una conversación para ver la traza
            </p>
          </div>
        ) : isLoadingTrace ? (
          <div className="flex-1 space-y-3 overflow-y-auto">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-16 bg-slate-100 animate-pulse rounded-lg" />
            ))}
          </div>
        ) : traceError ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {traceError}
            <button
              onClick={() => { clearTrace(); setSelectedLeadId(null) }}
              className="ml-3 text-red-500 underline"
            >
              Cerrar
            </button>
          </div>
        ) : selectedTrace ? (
          <>
            {/* Summary */}
            <div className="rounded-xl border border-slate-200 p-4 bg-white">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    {selectedTrace.summary.lead_name}
                  </h3>
                  <p className="text-xs text-slate-500">
                    Etapa: {selectedTrace.summary.current_stage} · Agente:{' '}
                    {selectedTrace.summary.current_agent}
                  </p>
                </div>
                <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showPrompts}
                    onChange={(e) => setShowPrompts(e.target.checked)}
                    className="rounded"
                  />
                  Ver prompts
                </label>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <p className="text-xs text-slate-500">Mensajes</p>
                  <p className="text-lg font-bold text-slate-900">
                    {selectedTrace.summary.total_messages}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Tokens</p>
                  <p className="text-lg font-bold text-slate-900">
                    {selectedTrace.summary.total_tokens.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Costo LLM</p>
                  <p className="text-lg font-bold text-slate-900">
                    ${selectedTrace.summary.total_cost_usd.toFixed(4)}
                  </p>
                </div>
              </div>
            </div>

            {/* Timeline */}
            <div className="flex-1 overflow-y-auto space-y-2">
              {selectedTrace.timeline.map((item) => (
                <TraceItemRow key={item.id} item={item} showPrompts={showPrompts} />
              ))}
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
