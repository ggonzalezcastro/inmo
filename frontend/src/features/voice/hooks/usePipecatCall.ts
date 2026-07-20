import { useState, useRef, useCallback } from 'react'
import { toast } from 'sonner'
import { useWebSocketEvent } from '@/shared/context/WebSocketContext'
import type { WSEvent } from '@/shared/context/WebSocketContext'
import { pipecatService } from '../services/pipecat.service'
import type { PipecatMode, TranscriptLine, CallSummary } from '../services/pipecat.service'
import type { CallPurpose } from '../types'

export type CallState = 'idle' | 'starting' | 'ringing' | 'active' | 'ending' | 'ended' | 'error'

export interface AiNote {
  note: string
  turn_count: number
  ts: number
}

export interface CoachingSuggestion {
  suggestion: string
  turn_count: number
  ts: number
}

export interface HandoffEvent {
  reason: string
  handoff_at: string
}

interface UsePipecatCallOptions {
  leadId: number
}

export function usePipecatCall({ leadId }: UsePipecatCallOptions) {
  const [callState, setCallState] = useState<CallState>('idle')
  const [voiceCallId, setVoiceCallId] = useState<number | null>(null)
  const [mode, setMode] = useState<PipecatMode | null>(null)
  const [transcript, setTranscript] = useState<TranscriptLine[]>([])
  const [aiNotes, setAiNotes] = useState<AiNote[]>([])
  const [suggestions, setSuggestions] = useState<CoachingSuggestion[]>([])
  const [handoff, setHandoff] = useState<HandoffEvent | null>(null)
  const [aiMuted, setAiMuted] = useState(false)
  const [summary, setSummary] = useState<CallSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  const callIdRef = useRef<number | null>(null)

  useWebSocketEvent(
    useCallback((event: WSEvent) => {
      const id = callIdRef.current
      if (!id) return

      if (event.type === 'call_answered') {
        const d = event.data as { voice_call_id: number }
        if (d.voice_call_id === id) setCallState('active')
      }

      if (event.type === 'call_transcript_line') {
        const d = event.data as { voice_call_id: number } & TranscriptLine
        if (d.voice_call_id === id) {
          setTranscript((prev) => [
            ...prev,
            {
              speaker: d.speaker,
              text: d.text,
              timestamp: d.timestamp,
              emotion_tag_used: d.emotion_tag_used,
              emotion_detected: d.emotion_detected,
            },
          ])
        }
      }

      if (event.type === 'call_ai_note') {
        const d = event.data as { voice_call_id: number; note: string; turn_count: number }
        if (d.voice_call_id === id) {
          setAiNotes((prev) => [...prev, { note: d.note, turn_count: d.turn_count, ts: Date.now() }])
        }
      }

      if (event.type === 'call_coaching_suggestion') {
        const d = event.data as { voice_call_id: number; suggestion: string; turn_count: number }
        if (d.voice_call_id === id) {
          setSuggestions((prev) => [
            ...prev,
            { suggestion: d.suggestion, turn_count: d.turn_count, ts: Date.now() },
          ])
        }
      }

      if (event.type === 'call_handoff') {
        const d = event.data as { voice_call_id: number; reason: string; handoff_at: string }
        if (d.voice_call_id === id) {
          setHandoff({ reason: d.reason, handoff_at: d.handoff_at })
          toast.info(`Handoff: ${d.reason}`)
        }
      }

      if (event.type === 'call_ended') {
        const d = event.data as { voice_call_id: number }
        if (d.voice_call_id === id) {
          setCallState('ended')
          _fetchSummary(id)
        }
      }
    }, [])
  )

  const _fetchSummary = useCallback(async (id: number) => {
    try {
      const data = await pipecatService.getSummary(id)
      setSummary(data)
    } catch {
      // summary may not be ready yet — non-fatal
    }
  }, [])

  const startCall = useCallback(
    async (callMode: PipecatMode, agentPhone?: string, purpose?: CallPurpose) => {
      setCallState('starting')
      setError(null)
      setTranscript([])
      setAiNotes([])
      setSuggestions([])
      setHandoff(null)
      setSummary(null)
      setAiMuted(false)

      try {
        let response
        if (callMode === 'autonomous') response = await pipecatService.startAutonomous(leadId, purpose)
        else if (callMode === 'copilot') response = await pipecatService.startCopilot(leadId, agentPhone, purpose)
        else if (callMode === 'handoff') response = await pipecatService.startHandoff(leadId, agentPhone, purpose)
        else response = await pipecatService.startCoaching(leadId, agentPhone, purpose)

        setVoiceCallId(response.voice_call_id)
        callIdRef.current = response.voice_call_id
        setMode(callMode)
        setCallState('ringing')
        toast.success('Llamada iniciada — esperando que el lead conteste…')
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'No se pudo iniciar la llamada'
        setError(msg)
        setCallState('error')
        toast.error(msg)
      }
    },
    [leadId]
  )

  const endCall = useCallback(async () => {
    if (!callIdRef.current) return
    setCallState('ending')
    try {
      await pipecatService.endCall(callIdRef.current)
    } catch {
      // best effort
    }
    setCallState('ended')
    if (callIdRef.current) _fetchSummary(callIdRef.current)
  }, [_fetchSummary])

  const toggleMuteAI = useCallback(async () => {
    if (!callIdRef.current) return
    try {
      if (aiMuted) {
        await pipecatService.unmuteAI(callIdRef.current)
        setAiMuted(false)
      } else {
        await pipecatService.muteAI(callIdRef.current)
        setAiMuted(true)
      }
    } catch {
      toast.error('Error al cambiar estado del micrófono IA')
    }
  }, [aiMuted])

  const refreshSummary = useCallback(() => {
    if (callIdRef.current) _fetchSummary(callIdRef.current)
  }, [_fetchSummary])

  const reset = useCallback(() => {
    setCallState('idle')
    setVoiceCallId(null)
    setMode(null)
    setTranscript([])
    setAiNotes([])
    setSuggestions([])
    setHandoff(null)
    setSummary(null)
    setAiMuted(false)
    setError(null)
    callIdRef.current = null
  }, [])

  return {
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
  }
}
