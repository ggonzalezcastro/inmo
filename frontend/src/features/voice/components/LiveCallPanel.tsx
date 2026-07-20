/**
 * LiveCallPanel — presentational panel for a live Pipecat call.
 *
 * Renders live transcript, AI notes (copilot), coaching suggestions,
 * and the post-call summary. Fed directly by usePipecatCall() return
 * values. Extracted from VoiceTestPage so LlamadasPage shares it.
 */
import { useEffect, useRef } from 'react'
import { RefreshCw, GitBranch } from 'lucide-react'
import { Button } from '@/shared/components/ui/button'
import type { PipecatMode, TranscriptLine, CallSummary } from '../services/pipecat.service'
import type { AiNote, CoachingSuggestion, HandoffEvent, CallState } from '../hooks/usePipecatCall'

const SPEAKER_LABEL: Record<string, string> = {
  customer: 'Lead',
  bot: 'IA',
  agent: 'Agente',
}

const SPEAKER_COLOR: Record<string, string> = {
  customer: 'text-slate-700',
  bot: 'text-violet-700',
  agent: 'text-blue-700',
}

export interface LiveCallPanelProps {
  callState: CallState
  mode: PipecatMode | null
  transcript: TranscriptLine[]
  aiNotes: AiNote[]
  suggestions: CoachingSuggestion[]
  summary: CallSummary | null
  refreshSummary: () => void
}

export function HandoffBanner({ handoff }: { handoff: HandoffEvent }) {
  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 space-y-1">
      <p className="text-xs font-semibold text-amber-800 flex items-center gap-1.5">
        <GitBranch className="h-3.5 w-3.5" />
        Handoff ejecutado
      </p>
      <p className="text-xs text-amber-700">{handoff.reason}</p>
      <p className="text-xs text-amber-600">
        {new Date(handoff.handoff_at).toLocaleTimeString('es-CL')}
      </p>
    </div>
  )
}

export function LiveCallPanel({
  callState,
  mode,
  transcript,
  aiNotes,
  suggestions,
  summary,
  refreshSummary,
}: LiveCallPanelProps) {
  const transcriptEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  const isCallActive = callState === 'ringing' || callState === 'active'
  const isCallDone = callState === 'ended'

  return (
    <div className="space-y-4">
      {/* Transcript */}
      <div className="rounded-xl border bg-card">
        <div className="px-4 py-3 border-b flex items-center justify-between">
          <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wide">
            Transcripción en vivo
          </p>
          <span className="text-xs text-muted-foreground">{transcript.length} líneas</span>
        </div>
        <div className="h-64 overflow-y-auto px-4 py-3 space-y-2">
          {transcript.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center mt-8">
              {isCallActive ? 'Esperando audio…' : 'Sin transcripción aún'}
            </p>
          ) : (
            transcript.map((line, i) => (
              <div key={i} className="text-xs">
                <span className={`font-semibold ${SPEAKER_COLOR[line.speaker] ?? 'text-foreground'}`}>
                  {SPEAKER_LABEL[line.speaker] ?? line.speaker}:
                </span>{' '}
                <span>{line.text}</span>
                {line.emotion_tag_used && (
                  <span className="ml-2 text-violet-400 italic">{line.emotion_tag_used}</span>
                )}
              </div>
            ))
          )}
          <div ref={transcriptEndRef} />
        </div>
      </div>

      {/* AI Notes (copilot) */}
      {(mode === 'copilot' || aiNotes.length > 0) && (
        <div className="rounded-xl border bg-card">
          <div className="px-4 py-3 border-b">
            <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wide">
              Notas automáticas IA{' '}
              <span className="normal-case font-normal">(copilot — cada 4 turnos)</span>
            </p>
          </div>
          <div className="max-h-48 overflow-y-auto px-4 py-3 space-y-2">
            {aiNotes.length === 0 ? (
              <p className="text-xs text-muted-foreground">Sin notas todavía…</p>
            ) : (
              [...aiNotes].reverse().map((n, i) => (
                <div key={i} className="rounded-lg bg-blue-50 border border-blue-100 p-2.5">
                  <p className="text-xs text-blue-800">{n.note}</p>
                  <p className="text-xs text-blue-400 mt-1">Turno {n.turn_count}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Coaching Suggestions */}
      {(mode === 'coaching' || suggestions.length > 0) && (
        <div className="rounded-xl border bg-card">
          <div className="px-4 py-3 border-b">
            <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wide">
              Sugerencias coaching{' '}
              <span className="normal-case font-normal">(cada 3 turnos — el lead no escucha)</span>
            </p>
          </div>
          <div className="max-h-48 overflow-y-auto px-4 py-3 space-y-2">
            {suggestions.length === 0 ? (
              <p className="text-xs text-muted-foreground">Sin sugerencias todavía…</p>
            ) : (
              [...suggestions].reverse().map((s, i) => (
                <div key={i} className="rounded-lg bg-violet-50 border border-violet-100 p-2.5">
                  <p className="text-xs text-violet-800">{s.suggestion}</p>
                  <p className="text-xs text-violet-400 mt-1">Turno {s.turn_count}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Post-call Summary */}
      {isCallDone && (
        <div className="rounded-xl border bg-card">
          <div className="px-4 py-3 border-b flex items-center justify-between">
            <p className="text-xs font-semibold uppercase text-muted-foreground tracking-wide">
              Resumen post-llamada
            </p>
            <Button variant="ghost" size="sm" className="h-6 px-2 gap-1 text-xs" onClick={refreshSummary}>
              <RefreshCw className="h-3 w-3" />
              Actualizar
            </Button>
          </div>
          <div className="px-4 py-4">
            {!summary ? (
              <p className="text-xs text-muted-foreground">
                Procesando… puede tomar unos segundos. Pulsa Actualizar.
              </p>
            ) : (
              <div className="space-y-4">
                {summary.summary && (
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground mb-1">Resumen</p>
                    <p className="text-sm">{summary.summary}</p>
                  </div>
                )}

                {summary.extracted_data && Object.keys(summary.extracted_data).length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground mb-2">
                      Datos extraídos
                    </p>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                      {Object.entries(summary.extracted_data)
                        .filter(([, v]) => v != null)
                        .map(([key, val]) => (
                          <div key={key} className="text-xs">
                            <span className="font-medium text-muted-foreground capitalize">
                              {key.replace(/_/g, ' ')}:{' '}
                            </span>
                            <span>{String(val)}</span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                {summary.call_metrics && (
                  <div>
                    <p className="text-xs font-semibold text-muted-foreground mb-2">Métricas</p>
                    <div className="grid grid-cols-3 gap-2">
                      {Object.entries(summary.call_metrics).map(([key, val]) => (
                        <div
                          key={key}
                          className="rounded-lg border bg-muted/40 px-3 py-2 text-center"
                        >
                          <p className="text-lg font-bold">{String(val)}</p>
                          <p className="text-xs text-muted-foreground capitalize">
                            {key.replace(/_/g, ' ')}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {summary.handoff_occurred && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    Handoff ocurrido: {summary.handoff_reason ?? '—'}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
