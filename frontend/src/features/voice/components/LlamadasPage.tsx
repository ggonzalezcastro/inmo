/**
 * LlamadasPage — production calls page.
 *
 * Pick a lead (search), motivo (CallPurpose) and modo (Pipecat), start the
 * call, watch it live (transcript / AI notes / coaching), and review broker
 * call history + metrics below.
 */
import { useCallback, useEffect, useState } from 'react'
import {
  Phone,
  PhoneOff,
  Mic,
  MicOff,
  Loader2,
  AlertTriangle,
} from 'lucide-react'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select'
import { Badge } from '@/shared/components/ui/badge'
import { LeadSearchCombobox } from '@/features/appointments/components/LeadSearchCombobox'
import { usePipecatCall } from '../hooks/usePipecatCall'
import type { PipecatMode, CallListItem, CallMetrics } from '../services/pipecat.service'
import { pipecatService } from '../services/pipecat.service'
import { CALL_PURPOSE_LABELS } from '../types'
import type { CallPurpose } from '../types'
import { MODES, STATE_BADGE } from './pipecatModes'
import { LiveCallPanel, HandoffBanner } from './LiveCallPanel'
import { CallMetricsCards } from './CallMetricsCards'
import { CallHistoryTable } from './CallHistoryTable'

interface LeadOption {
  id: number
  name: string
  phone: string
  email?: string
}

const PAGE_SIZE = 10

export function LlamadasPage() {
  const [selectedLead, setSelectedLead] = useState<LeadOption | null>(null)
  const [purpose, setPurpose] = useState<CallPurpose>('confirmacion_visita')
  const [selectedMode, setSelectedMode] = useState<PipecatMode>('autonomous')
  const [agentPhone, setAgentPhone] = useState('')

  // History + metrics
  const [historyItems, setHistoryItems] = useState<CallListItem[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyPage, setHistoryPage] = useState(1)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [metrics, setMetrics] = useState<CallMetrics | null>(null)
  const [loadingMetrics, setLoadingMetrics] = useState(true)

  const {
    callState,
    voiceCallId,
    mode,
    transcript,
    aiNotes,
    suggestions,
    handoff,
    aiMuted,
    summary,
    error,
    startCall,
    endCall,
    toggleMuteAI,
    refreshSummary,
    reset,
  } = usePipecatCall({ leadId: selectedLead?.id ?? 0 })

  const fetchHistory = useCallback(async (page: number) => {
    setLoadingHistory(true)
    try {
      const res = await pipecatService.listCalls({
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      })
      setHistoryItems(res.data)
      setHistoryTotal(res.total)
    } catch {
      setHistoryItems([])
      setHistoryTotal(0)
    } finally {
      setLoadingHistory(false)
    }
  }, [])

  const fetchMetrics = useCallback(async () => {
    setLoadingMetrics(true)
    try {
      setMetrics(await pipecatService.getMetrics())
    } catch {
      setMetrics(null)
    } finally {
      setLoadingMetrics(false)
    }
  }, [])

  useEffect(() => {
    void fetchHistory(historyPage)
  }, [historyPage, fetchHistory])

  useEffect(() => {
    void fetchMetrics()
  }, [fetchMetrics])

  // Refresh history + metrics when a call finishes
  useEffect(() => {
    if (callState === 'ended') {
      void fetchHistory(1)
      setHistoryPage(1)
      void fetchMetrics()
    }
  }, [callState, fetchHistory, fetchMetrics])

  const selectedModeInfo = MODES.find((m) => m.value === selectedMode)!
  const isCallActive = callState === 'ringing' || callState === 'active'
  const isCallDone = callState === 'ended'
  const canStart = callState === 'idle' || callState === 'ended' || callState === 'error'
  const showAiControls = (mode === 'autonomous' || mode === 'handoff') && isCallActive
  const stateBadge = STATE_BADGE[callState]
  const leadHasPhone = Boolean(selectedLead?.phone)

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-green-100">
          <Phone className="h-5 w-5 text-green-600" />
        </div>
        <div>
          <h1 className="text-xl font-semibold">Llamadas</h1>
          <p className="text-sm text-muted-foreground">
            Llama a un lead con IA: elige a quién, el motivo y el tipo de llamada
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Badge variant={stateBadge.variant}>{stateBadge.label}</Badge>
          {voiceCallId && (
            <span className="text-xs text-muted-foreground">llamada #{voiceCallId}</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Left: Config Panel ── */}
        <div className="space-y-5 lg:col-span-1">
          <div className="rounded-xl border bg-card p-4 space-y-4">
            <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wide">
              Nueva llamada
            </p>

            {/* Lead selector */}
            <div className="space-y-1.5">
              <Label className="text-xs">¿A quién llamar?</Label>
              <LeadSearchCombobox
                value={selectedLead}
                onChange={(lead) => {
                  if (canStart) setSelectedLead(lead)
                }}
                placeholder="Buscar lead por nombre o teléfono…"
              />
              {selectedLead && !leadHasPhone && (
                <p className="text-xs text-red-600">Este lead no tiene teléfono registrado.</p>
              )}
            </div>

            {/* Purpose selector */}
            <div className="space-y-1.5">
              <Label htmlFor="purpose-select" className="text-xs">
                Motivo de la llamada
              </Label>
              <Select
                value={purpose}
                onValueChange={(v) => setPurpose(v as CallPurpose)}
                disabled={!canStart}
              >
                <SelectTrigger id="purpose-select" className="w-full text-sm">
                  <SelectValue placeholder="Seleccionar motivo…" />
                </SelectTrigger>
                <SelectContent>
                  {(Object.entries(CALL_PURPOSE_LABELS) as [CallPurpose, string][]).map(
                    ([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    )
                  )}
                </SelectContent>
              </Select>
            </div>

            {/* Mode selector */}
            <div className="space-y-1.5">
              <Label className="text-xs">Tipo de llamada</Label>
              <div className="grid grid-cols-2 gap-2">
                {MODES.map((m) => (
                  <button
                    key={m.value}
                    type="button"
                    disabled={!canStart}
                    onClick={() => setSelectedMode(m.value)}
                    className={`rounded-lg border p-2.5 text-left transition-colors text-xs disabled:opacity-40 ${
                      selectedMode === m.value
                        ? 'border-green-500 bg-green-50 ring-1 ring-green-400'
                        : 'border-border hover:bg-muted'
                    }`}
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <m.icon className="h-3.5 w-3.5 text-green-600 shrink-0" />
                      <span className="font-semibold">{m.label}</span>
                    </div>
                    <p className="text-muted-foreground leading-snug">{m.description}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Agent phone */}
            {selectedModeInfo.needsAgentPhone && (
              <div className="space-y-1.5">
                <Label htmlFor="agent-phone" className="text-xs">
                  Teléfono agente{' '}
                  <span className="text-muted-foreground">
                    (para conectar al humano en este modo)
                  </span>
                </Label>
                <Input
                  id="agent-phone"
                  placeholder="+56912345678"
                  value={agentPhone}
                  onChange={(e) => setAgentPhone(e.target.value)}
                  disabled={!canStart}
                  className="text-sm"
                />
              </div>
            )}

            {/* Actions */}
            <div className="pt-1 space-y-2">
              {canStart ? (
                <Button
                  className="w-full bg-green-600 hover:bg-green-700 text-white gap-2"
                  disabled={!selectedLead || !leadHasPhone}
                  onClick={() => startCall(selectedMode, agentPhone || undefined, purpose)}
                >
                  <Phone className="h-4 w-4" />
                  Llamar
                </Button>
              ) : (
                <Button
                  variant="destructive"
                  className="w-full gap-2"
                  disabled={callState === 'ending' || callState === 'starting'}
                  onClick={endCall}
                >
                  {callState === 'ending' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <PhoneOff className="h-4 w-4" />
                  )}
                  {callState === 'ending' ? 'Finalizando…' : 'Colgar'}
                </Button>
              )}

              {showAiControls && (
                <Button
                  variant="outline"
                  className={`w-full gap-2 text-xs ${aiMuted ? 'border-amber-400 text-amber-600' : ''}`}
                  onClick={toggleMuteAI}
                >
                  {aiMuted ? <MicOff className="h-3.5 w-3.5" /> : <Mic className="h-3.5 w-3.5" />}
                  {aiMuted ? 'Activar IA' : 'Silenciar IA'}
                </Button>
              )}

              {isCallDone && (
                <Button variant="ghost" className="w-full gap-2 text-xs" onClick={reset}>
                  Nueva llamada
                </Button>
              )}
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 p-3 text-xs text-red-700">
                <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                {error}
              </div>
            )}
          </div>

          {/* Handoff event */}
          {handoff && <HandoffBanner handoff={handoff} />}
        </div>

        {/* ── Right: Live Data ── */}
        <div className="lg:col-span-2">
          <LiveCallPanel
            callState={callState}
            mode={mode}
            transcript={transcript}
            aiNotes={aiNotes}
            suggestions={suggestions}
            summary={summary}
            refreshSummary={refreshSummary}
          />
        </div>
      </div>

      {/* ── Metrics + History ── */}
      <CallMetricsCards metrics={metrics} loading={loadingMetrics} />
      <CallHistoryTable
        items={historyItems}
        total={historyTotal}
        page={historyPage}
        pageSize={PAGE_SIZE}
        loading={loadingHistory}
        onPageChange={setHistoryPage}
      />
    </div>
  )
}
