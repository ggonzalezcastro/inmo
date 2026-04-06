import { useEffect, useRef, useState, useCallback } from 'react'
import { Play, Pause, Trash2, Wifi, WifiOff } from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface LiveEvent {
  id: string
  ts: string
  event_type: string
  agent_type?: string
  broker_id?: number
  lead_id?: number
  message?: string
  error_type?: string
  from_agent?: string
  to_agent?: string
  reason?: string
  latency_ms?: number
  cost_usd?: number
  tokens?: number
  [key: string]: unknown
}

// ── Constants ─────────────────────────────────────────────────────────────────

const EVENT_TYPES = [
  'agent_selected',
  'handoff',
  'llm_call',
  'error',
  'escalation',
  'tool_call',
  'pipeline_stage',
] as const

const AGENT_TYPES = ['qualifier', 'scheduler', 'follow_up', 'property', 'supervisor'] as const

const EVENT_COLORS: Record<string, string> = {
  agent_selected: 'text-blue-400',
  handoff:        'text-yellow-400',
  llm_call:       'text-green-400',
  error:          'text-red-400',
  escalation:     'text-orange-400',
  tool_call:      'text-purple-400',
  pipeline_stage: 'text-cyan-400',
  heartbeat:      'text-slate-600',
  pong:           'text-slate-600',
}

const EVENT_BADGES: Record<string, string> = {
  agent_selected: 'bg-blue-900/60 text-blue-300 border-blue-800',
  handoff:        'bg-yellow-900/60 text-yellow-300 border-yellow-800',
  llm_call:       'bg-green-900/60 text-green-300 border-green-800',
  error:          'bg-red-900/60 text-red-300 border-red-800',
  escalation:     'bg-orange-900/60 text-orange-300 border-orange-800',
  tool_call:      'bg-purple-900/60 text-purple-300 border-purple-800',
  pipeline_stage: 'bg-cyan-900/60 text-cyan-300 border-cyan-800',
}

const MAX_LINES = 500

// ── Helpers ───────────────────────────────────────────────────────────────────

// Backend WS base — mirrors WebSocketContext.tsx approach
const BASE_WS = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/^http/, 'ws')

function buildWsUrl(brokerId: string, eventTypes: string[], agentType: string): string {
  const params = new URLSearchParams()
  if (brokerId) params.set('broker_id', brokerId)
  if (eventTypes.length > 0) params.set('event_type', eventTypes.join(','))
  if (agentType) params.set('agent_type', agentType)
  const qs = params.toString()
  return `${BASE_WS}/ws/admin/observability/live${qs ? '?' + qs : ''}`
}

function formatEventLine(ev: LiveEvent): string {
  const parts: string[] = []
  if (ev.agent_type) parts.push(`[${ev.agent_type}]`)
  if (ev.lead_id)    parts.push(`lead=${ev.lead_id}`)
  if (ev.broker_id)  parts.push(`broker=${ev.broker_id}`)

  switch (ev.event_type) {
    case 'handoff':
      parts.push(`${ev.from_agent ?? '?'} → ${ev.to_agent ?? '?'}`)
      if (ev.reason) parts.push(`reason="${ev.reason}"`)
      break
    case 'llm_call':
      if (ev.latency_ms != null) parts.push(`${ev.latency_ms}ms`)
      if (ev.tokens != null)     parts.push(`${ev.tokens}tok`)
      if (ev.cost_usd != null)   parts.push(`$${Number(ev.cost_usd).toFixed(5)}`)
      break
    case 'error':
      if (ev.error_type) parts.push(ev.error_type)
      if (ev.message)    parts.push(`"${ev.message}"`)
      break
    case 'escalation':
      if (ev.reason)  parts.push(`reason="${ev.reason}"`)
      break
    default:
      if (ev.message) parts.push(`"${ev.message}"`)
  }

  return parts.join('  ')
}

// ── Main component ────────────────────────────────────────────────────────────

export function LiveTailPanel() {
  const [lines, setLines] = useState<LiveEvent[]>([])
  const [connected, setConnected] = useState(false)
  const [paused, setPaused] = useState(false)
  const [brokerId, setBrokerId] = useState('')
  const [selectedEventTypes, setSelectedEventTypes] = useState<string[]>([])
  const [agentType, setAgentType] = useState('')

  const wsRef   = useRef<WebSocket | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)
  const pausedRef = useRef(paused)
  pausedRef.current = paused

  const appendLine = useCallback((ev: LiveEvent) => {
    if (pausedRef.current) return
    setLines((prev) => {
      const next = [...prev, ev]
      return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next
    })
  }, [])

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const url = buildWsUrl(brokerId, selectedEventTypes, agentType)
    const ws  = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      wsRef.current = null
    }
    ws.onerror = () => setConnected(false)
    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data)
        if (data.type === 'heartbeat' || data.type === 'pong') return
        const ev: LiveEvent = {
          id: `${Date.now()}-${Math.random()}`,
          ts: data.created_at ?? new Date().toISOString(),
          event_type: data.event_type ?? data.type ?? 'unknown',
          ...data,
        }
        appendLine(ev)
      } catch {
        // ignore malformed frames
      }
    }

    // Keep-alive ping every 25 s
    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 25_000)
    ws.addEventListener('close', () => clearInterval(ping))
  }, [brokerId, selectedEventTypes, agentType, appendLine])

  // Auto-connect on mount
  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll to bottom when new lines arrive
  useEffect(() => {
    if (!paused) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines, paused])

  function toggleEventType(et: string) {
    setSelectedEventTypes((prev) =>
      prev.includes(et) ? prev.filter((x) => x !== et) : [...prev, et]
    )
  }

  function handleApplyFilters() {
    connect()
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">Live Tail</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Eventos de agentes en tiempo real · máx. {MAX_LINES} líneas
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`flex items-center gap-1.5 text-xs font-medium ${connected ? 'text-green-600' : 'text-red-500'}`}>
            {connected ? <Wifi size={13} /> : <WifiOff size={13} />}
            {connected ? 'Conectado' : 'Desconectado'}
          </span>
          <button
            onClick={() => setPaused((p) => !p)}
            className={`flex items-center gap-1.5 h-8 px-3 rounded-lg border text-xs font-medium transition-colors ${
              paused
                ? 'border-yellow-300 bg-yellow-50 text-yellow-700 hover:bg-yellow-100'
                : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
            }`}
          >
            {paused ? <Play size={12} /> : <Pause size={12} />}
            {paused ? 'Reanudar' : 'Pausar'}
          </button>
          <button
            onClick={() => setLines([])}
            className="flex items-center gap-1.5 h-8 px-3 rounded-lg border border-slate-200 bg-white text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <Trash2 size={12} />
            Limpiar
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Filtros</p>
        <div className="flex flex-wrap gap-4 items-end">
          {/* Broker ID */}
          <div>
            <label className="block text-xs text-slate-500 mb-1">Broker ID</label>
            <input
              type="number"
              value={brokerId}
              onChange={(e) => setBrokerId(e.target.value)}
              placeholder="todos"
              className="h-8 w-28 rounded-lg border border-slate-200 px-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Agent type */}
          <div>
            <label className="block text-xs text-slate-500 mb-1">Agente</label>
            <select
              value={agentType}
              onChange={(e) => setAgentType(e.target.value)}
              className="h-8 rounded-lg border border-slate-200 px-2 text-sm text-slate-700 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Todos</option>
              {AGENT_TYPES.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>

          {/* Event types (multi-select chips) */}
          <div>
            <label className="block text-xs text-slate-500 mb-1">Tipos de evento</label>
            <div className="flex flex-wrap gap-1.5">
              {EVENT_TYPES.map((et) => {
                const active = selectedEventTypes.includes(et)
                return (
                  <button
                    key={et}
                    onClick={() => toggleEventType(et)}
                    className={`h-7 px-2.5 rounded-full text-xs font-medium border transition-colors ${
                      active
                        ? 'bg-slate-800 text-white border-slate-700'
                        : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
                    }`}
                  >
                    {et}
                  </button>
                )
              })}
              {selectedEventTypes.length > 0 && (
                <button
                  onClick={() => setSelectedEventTypes([])}
                  className="h-7 px-2 rounded-full text-xs text-slate-400 hover:text-slate-600"
                >
                  ✕ todos
                </button>
              )}
            </div>
          </div>

          <button
            onClick={handleApplyFilters}
            className="h-8 px-4 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 transition-colors"
          >
            Aplicar
          </button>
        </div>
      </div>

      {/* Terminal */}
      <div className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden">
        {/* Terminal header */}
        <div className="flex items-center gap-2 px-4 py-2 bg-slate-900 border-b border-slate-800">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/70" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/70" />
            <div className="w-3 h-3 rounded-full bg-green-500/70" />
          </div>
          <span className="text-xs text-slate-500 ml-2 font-mono">
            obs:live — {lines.length} eventos
            {paused && <span className="ml-2 text-yellow-400">[PAUSADO]</span>}
          </span>
        </div>

        {/* Log lines */}
        <div className="h-[480px] overflow-y-auto p-4 font-mono text-xs leading-6 space-y-0.5">
          {lines.length === 0 ? (
            <p className="text-slate-600 italic">
              {connected
                ? 'Esperando eventos… Los eventos aparecerán aquí en tiempo real.'
                : 'Sin conexión. Verifica que el backend esté corriendo.'}
            </p>
          ) : (
            lines.map((ev) => {
              const color = EVENT_COLORS[ev.event_type] ?? 'text-slate-300'
              const badge = EVENT_BADGES[ev.event_type]
              const time  = new Date(ev.ts).toLocaleTimeString('es-CL', { hour12: false })
              const detail = formatEventLine(ev)

              return (
                <div key={ev.id} className="flex items-start gap-2 group">
                  <span className="text-slate-600 shrink-0 tabular-nums">{time}</span>
                  {badge ? (
                    <span className={`shrink-0 rounded border px-1.5 text-[10px] font-semibold ${badge}`}>
                      {ev.event_type}
                    </span>
                  ) : (
                    <span className={`shrink-0 ${color}`}>{ev.event_type}</span>
                  )}
                  <span className={`${color} break-all`}>{detail}</span>
                </div>
              )
            })
          )}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  )
}
