/**
 * VoiceTestPage — dev/test panel for the Pipecat voice pipeline.
 *
 * Lets you pick a lead + mode, start a call, watch live transcript,
 * AI notes (copilot), coaching suggestions, handoff events, and
 * the post-call LLM summary.
 */
import { useEffect, useState } from 'react'
import {
  Phone,
  PhoneOff,
  Mic,
  MicOff,
  Loader2,
  FlaskConical,
  AlertTriangle,
} from 'lucide-react'
import { toast } from 'sonner'
import { apiClient } from '@/shared/lib/api-client'
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
import { usePipecatCall } from '../hooks/usePipecatCall'
import type { PipecatMode } from '../services/pipecat.service'
import { MODES, STATE_BADGE } from './pipecatModes'
import { LiveCallPanel, HandoffBanner } from './LiveCallPanel'

// ── Types ──────────────────────────────────────────────────────────────────

interface LeadOption {
  id: number
  name: string
  phone: string
}

// ── Component ──────────────────────────────────────────────────────────────

export function VoiceTestPage() {
  const [leads, setLeads] = useState<LeadOption[]>([])
  const [selectedLeadId, setSelectedLeadId] = useState<number | null>(null)
  const [selectedMode, setSelectedMode] = useState<PipecatMode>('autonomous')
  const [agentPhone, setAgentPhone] = useState('')
  const [loadingLeads, setLoadingLeads] = useState(true)

  const selectedLead = leads.find((l) => l.id === selectedLeadId) ?? null

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
  } = usePipecatCall({ leadId: selectedLeadId ?? 0 })

  // Load leads on mount
  useEffect(() => {
    apiClient
      .get<{ data: LeadOption[]; total: number }>('/api/v1/leads', {
        params: { limit: 50, offset: 0 },
      })
      .then((res) => {
        setLeads(Array.isArray(res.data) ? res.data : [])
      })
      .catch(() => toast.error('No se pudieron cargar los leads'))
      .finally(() => setLoadingLeads(false))
  }, [])

  const selectedModeInfo = MODES.find((m) => m.value === selectedMode)!
  const isCallActive = callState === 'ringing' || callState === 'active'
  const isCallDone = callState === 'ended'
  const canStart = callState === 'idle' || callState === 'ended' || callState === 'error'
  const showAiControls = (mode === 'autonomous' || mode === 'handoff') && isCallActive
  const stateBadge = STATE_BADGE[callState]

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-violet-100">
          <FlaskConical className="h-5 w-5 text-violet-600" />
        </div>
        <div>
          <h1 className="text-xl font-semibold">Test de Voz — Pipecat</h1>
          <p className="text-sm text-muted-foreground">
            Panel de pruebas para los 4 modos del pipeline de voz
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <Badge variant={stateBadge.variant}>{stateBadge.label}</Badge>
          {voiceCallId && (
            <span className="text-xs text-muted-foreground">call #{voiceCallId}</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ── Left: Config Panel ── */}
        <div className="space-y-5 lg:col-span-1">
          <div className="rounded-xl border bg-card p-4 space-y-4">
            <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wide">
              Configuración
            </p>

            {/* Lead selector */}
            <div className="space-y-1.5">
              <Label htmlFor="lead-select" className="text-xs">
                Lead
              </Label>
              {loadingLeads ? (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Cargando…
                </div>
              ) : (
                <Select
                  value={selectedLeadId ? String(selectedLeadId) : ''}
                  onValueChange={(v) => setSelectedLeadId(Number(v))}
                  disabled={!canStart}
                >
                  <SelectTrigger id="lead-select" className="w-full text-sm">
                    <SelectValue placeholder="Seleccionar lead…" />
                  </SelectTrigger>
                  <SelectContent>
                    {leads.map((l) => (
                      <SelectItem key={l.id} value={String(l.id)}>
                        <span className="font-medium">{l.name}</span>
                        {l.phone && (
                          <span className="ml-2 text-xs text-muted-foreground">{l.phone}</span>
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              {selectedLead?.phone && (
                <p className="text-xs text-muted-foreground">{selectedLead.phone}</p>
              )}
            </div>

            {/* Mode selector */}
            <div className="space-y-1.5">
              <Label className="text-xs">Modo</Label>
              <div className="grid grid-cols-2 gap-2">
                {MODES.map((m) => (
                  <button
                    key={m.value}
                    type="button"
                    disabled={!canStart}
                    onClick={() => setSelectedMode(m.value)}
                    className={`rounded-lg border p-2.5 text-left transition-colors text-xs disabled:opacity-40 ${
                      selectedMode === m.value
                        ? 'border-violet-500 bg-violet-50 ring-1 ring-violet-400'
                        : 'border-border hover:bg-muted'
                    }`}
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <m.icon className="h-3.5 w-3.5 text-violet-600 shrink-0" />
                      <span className="font-semibold">{m.label}</span>
                    </div>
                    <p className="text-muted-foreground leading-snug">{m.description}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Agent phone (optional) */}
            {selectedModeInfo.needsAgentPhone && (
              <div className="space-y-1.5">
                <Label htmlFor="agent-phone" className="text-xs">
                  Teléfono agente{' '}
                  <span className="text-muted-foreground">(opcional — para handoff/coaching)</span>
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
                  disabled={!selectedLeadId}
                  onClick={() => startCall(selectedMode, agentPhone || undefined)}
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
                  {aiMuted ? (
                    <MicOff className="h-3.5 w-3.5" />
                  ) : (
                    <Mic className="h-3.5 w-3.5" />
                  )}
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
    </div>
  )
}
