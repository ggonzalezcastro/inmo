/**
 * ActiveCallOverlay — floating panel displayed during an active call.
 * Shows: lead name, duration, live transcript, mute/hang-up controls.
 */
import { useEffect, useState } from 'react'
import { Phone, PhoneOff, Mic, MicOff, Loader2 } from 'lucide-react'
import { Button } from '@/shared/components/ui/button'
import type { CallState, TranscriptLine } from '../types'

interface ActiveCallOverlayProps {
  callState: CallState
  leadName: string
  leadPhone: string
  transcript: TranscriptLine[]
  isMuted: boolean
  onMuteToggle: () => void
  onEndCall: () => void
}

function useCallTimer(active: boolean) {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    if (!active) { setSeconds(0); return }
    const id = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [active])
  const m = Math.floor(seconds / 60).toString().padStart(2, '0')
  const s = (seconds % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

const SPEAKER_LABEL: Record<TranscriptLine['speaker'], string> = {
  agent: 'Agente',
  lead: 'Lead',
  bot: 'IA',
}

const SPEAKER_COLOR: Record<TranscriptLine['speaker'], string> = {
  agent: 'text-blue-700',
  lead: 'text-slate-700',
  bot: 'text-violet-700',
}

export function ActiveCallOverlay({
  callState,
  leadName,
  leadPhone,
  transcript,
  isMuted,
  onMuteToggle,
  onEndCall,
}: ActiveCallOverlayProps) {
  const timer = useCallTimer(callState === 'active')

  if (callState === 'idle' || callState === 'ended') return null

  const isStarting = callState === 'starting'
  const isEnding = callState === 'ending'

  return (
    <div className="fixed bottom-6 right-6 z-50 w-80 rounded-2xl border border-border bg-white shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="bg-green-600 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2 text-white min-w-0">
          {isStarting || isEnding ? (
            <Loader2 className="h-4 w-4 animate-spin shrink-0" />
          ) : (
            <Phone className="h-4 w-4 shrink-0" />
          )}
          <div className="min-w-0">
            <p className="text-sm font-semibold truncate">{leadName}</p>
            <p className="text-xs text-green-100">{isStarting ? 'Conectando…' : isEnding ? 'Finalizando…' : timer}</p>
          </div>
        </div>
        <span className="text-xs text-green-100 shrink-0">{leadPhone}</span>
      </div>

      {/* Transcript */}
      <div className="h-48 overflow-y-auto px-3 py-2">
        {transcript.length === 0 ? (
          <p className="text-xs text-muted-foreground text-center mt-8">
            {isStarting ? 'Iniciando transcripción…' : 'Esperando audio…'}
          </p>
        ) : (
          <div className="space-y-2">
            {transcript.map((line, i) => (
              <div key={i} className="text-xs">
                <span className={`font-semibold ${SPEAKER_COLOR[line.speaker]}`}>
                  {SPEAKER_LABEL[line.speaker]}:
                </span>{' '}
                <span className="text-foreground">{line.text}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="px-4 py-3 border-t border-border flex items-center justify-between">
        <Button
          variant="outline"
          size="sm"
          className={`gap-1.5 ${isMuted ? 'border-amber-400 text-amber-600 bg-amber-50' : ''}`}
          onClick={onMuteToggle}
          disabled={isStarting || isEnding}
        >
          {isMuted ? <MicOff className="h-3.5 w-3.5" /> : <Mic className="h-3.5 w-3.5" />}
          {isMuted ? 'Silenciado' : 'Micrófono'}
        </Button>

        <Button
          size="sm"
          className="bg-red-600 hover:bg-red-700 text-white gap-1.5"
          onClick={onEndCall}
          disabled={isEnding}
        >
          <PhoneOff className="h-3.5 w-3.5" />
          Colgar
        </Button>
      </div>
    </div>
  )
}
