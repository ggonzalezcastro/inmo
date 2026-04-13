/**
 * useVapiCall — manages the full lifecycle of a CRM-initiated voice call.
 *
 * Flow:
 *  1. startCall() → POST /calls/start → receives vapi_jwt + voice_call_id
 *  2. Initialises @vapi-ai/web SDK with the JWT
 *  3. Vapi SDK fires audio events; WS backend pushes call_transcript events
 *  4. endCall() → POST /calls/{id}/end + sdk.stop()
 */
import { useState, useRef, useCallback, useEffect } from 'react'
import Vapi from '@vapi-ai/web'
import { toast } from 'sonner'
import { useWebSocketEvent } from '@/shared/context/WebSocketContext'
import type { WSEvent } from '@/shared/context/WebSocketContext'
import { voiceService } from '../services/voice.service'
import type { CallMode, CallPurpose, CallState, TranscriptLine } from '../types'

interface UseVapiCallOptions {
  leadId: number
}

export function useVapiCall({ leadId }: UseVapiCallOptions) {
  const [callState, setCallState] = useState<CallState>('idle')
  const [voiceCallId, setVoiceCallId] = useState<number | null>(null)
  const [transcript, setTranscript] = useState<TranscriptLine[]>([])
  const [isMuted, setIsMuted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const vapiRef = useRef<Vapi | null>(null)
  const callIdRef = useRef<number | null>(null)

  // ── WS events from backend (transcript + status) ──────────────────────────
  useWebSocketEvent(
    useCallback(
      (event: WSEvent) => {
        if (!callIdRef.current) return

        if (event.type === 'call_transcript') {
          const data = event.data as { call_id: number; transcript: string | null }
          if (data.call_id !== callIdRef.current) return
          if (!data.transcript) return
          setTranscript((prev) => [
            ...prev,
            { speaker: 'bot', text: data.transcript!, ts: Date.now() },
          ])
        }

        if (event.type === 'call_status') {
          const data = event.data as { call_id: number; status: string }
          if (data.call_id !== callIdRef.current) return
          if (data.status === 'ended' || data.status === 'failed') {
            setCallState('ended')
          }
        }
      },
      []
    )
  )

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (vapiRef.current) {
        try { vapiRef.current.stop() } catch {}
      }
    }
  }, [])

  // ── Start call ────────────────────────────────────────────────────────────
  const startCall = useCallback(
    async (callMode: CallMode, callPurpose: CallPurpose) => {
      if (callState !== 'idle' && callState !== 'ended' && callState !== 'error') return
      setCallState('starting')
      setError(null)
      setTranscript([])

      try {
        const response = await voiceService.startCall({
          lead_id: leadId,
          call_mode: callMode,
          call_purpose: callPurpose,
        })

        setVoiceCallId(response.voice_call_id)
        callIdRef.current = response.voice_call_id

        // Autonomous mode: VAPI already called the lead — no SDK session needed.
        if (response.call_mode === 'autonomous') {
          setCallState('active')
          return
        }

        // Initialise VAPI SDK with the Public Key (browser-safe, read-only for call initiation)
        const vapi = new Vapi(response.vapi_public_key!)
        vapiRef.current = vapi

        vapi.on('call-start', async (callData?: { id?: string }) => {
          setCallState('active')
          // Link the VAPI-assigned call ID back to our VoiceCall row so that
          // backend webhook handlers can look up the call by external_call_id.
          const externalId = callData?.id
          if (externalId && callIdRef.current) {
            try {
              await voiceService.linkExternalId(callIdRef.current, externalId)
            } catch {
              // Non-fatal: webhook processing will fail gracefully without it
              console.warn('[useVapiCall] Failed to link external_call_id', externalId)
            }
          }
        })

        vapi.on('call-end', () => {
          setCallState('ended')
          vapiRef.current = null
        })

        vapi.on('error', (err: unknown) => {
          const msg = err instanceof Error ? err.message : 'Error en llamada VAPI'
          setError(msg)
          setCallState('error')
          toast.error(`Error VAPI: ${msg}`)
          vapiRef.current = null
        })

        // Live transcript from VAPI SDK (client-side speech-to-text)
        vapi.on('message', (msg: { type: string; role?: string; transcript?: string; transcriptType?: string }) => {
          if (msg.type === 'transcript' && msg.transcript && msg.transcriptType === 'final') {
            const speaker: TranscriptLine['speaker'] = msg.role === 'assistant' ? 'bot' : 'agent'
            setTranscript((prev) => [
              ...prev,
              { speaker, text: msg.transcript!, ts: Date.now() },
            ])
          }
        })

        // AssistantId flow: prompt lives server-side, only the ID + per-call
        // overrides (tools) reach the browser. Fallback to inline config when
        // the agent has no profile (bare transcriptor mode).
        //
        // Inject metadata.call_id so the webhook handler can look up the
        // VoiceCall row by metadata before external_call_id is linked.
        const metadataOverride = { call: { metadata: { call_id: response.voice_call_id } } }

        if (response.vapi_assistant_id) {
          const overrides = {
            ...(response.assistant_overrides ?? {}),
            ...metadataOverride,
          } as Parameters<Vapi['start']>[1]
          await vapi.start(response.vapi_assistant_id, overrides)
        } else {
          const fallbackConfig = {
            ...(response.vapi_config ?? {
              transcriber: { provider: 'deepgram', model: 'nova-2', language: 'es' },
            }),
            ...metadataOverride,
          }
          await vapi.start(fallbackConfig as Parameters<Vapi['start']>[0])
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'No se pudo iniciar la llamada'
        setError(msg)
        setCallState('error')
        toast.error(msg)
        callIdRef.current = null
      }
    },
    [leadId, callState]
  )

  // ── End call ──────────────────────────────────────────────────────────────
  const endCall = useCallback(async () => {
    setCallState('ending')
    try {
      if (vapiRef.current) {
        vapiRef.current.stop()
        vapiRef.current = null
      }
      if (callIdRef.current) {
        await voiceService.endCall(callIdRef.current)
      }
    } catch {
      // best effort
    } finally {
      setCallState('ended')
    }
  }, [])

  // ── Mute toggle ───────────────────────────────────────────────────────────
  const toggleMute = useCallback(() => {
    if (!vapiRef.current) return
    const next = !isMuted
    vapiRef.current.setMuted(next)
    setIsMuted(next)
  }, [isMuted])

  // ── Reset to idle after ended ─────────────────────────────────────────────
  const reset = useCallback(() => {
    setCallState('idle')
    setVoiceCallId(null)
    setTranscript([])
    setIsMuted(false)
    setError(null)
    callIdRef.current = null
    vapiRef.current = null
  }, [])

  return {
    callState,
    voiceCallId,
    transcript,
    isMuted,
    error,
    startCall,
    endCall,
    toggleMute,
    reset,
  }
}
