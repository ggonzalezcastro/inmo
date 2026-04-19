import { useState, useEffect, useRef, useCallback } from 'react'
import { useWebSocketEvent, type WSEvent } from '@/shared/context/WebSocketContext'

export type SofiaStatus = 'idle' | 'receiving' | 'thinking' | 'responded' | 'stage_change' | 'hot_lead'

export interface SofiaActivity {
  status: SofiaStatus
  label: string
  detail: string
  /** Accumulated event count since page load */
  eventCount: number
}

const STAGE_LABELS: Record<string, string> = {
  entrada:                  'Entrada',
  perfilamiento:            'Perfilamiento',
  calificacion_financiera:  'Calificación financiera',
  potencial:                'Potencial',
  agendado:                 'Agendado',
  ganado:                   'Ganado',
  perdido:                  'Perdido',
}

const IDLE_MESSAGES = [
  'Monitoreando conversaciones',
  'Lista para responder',
  'Analizando leads',
  'En espera de mensajes',
]

export function useSofiaActivity(): SofiaActivity {
  const [status, setStatus] = useState<SofiaStatus>('idle')
  const [label, setLabel] = useState(IDLE_MESSAGES[0])
  const [detail, setDetail] = useState('')
  const [eventCount, setEventCount] = useState(0)
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const idleIndexRef = useRef(0)

  const scheduleReset = useCallback((ms: number) => {
    if (resetTimerRef.current) clearTimeout(resetTimerRef.current)
    resetTimerRef.current = setTimeout(() => {
      idleIndexRef.current = (idleIndexRef.current + 1) % IDLE_MESSAGES.length
      setStatus('idle')
      setLabel(IDLE_MESSAGES[idleIndexRef.current])
      setDetail('')
    }, ms)
  }, [])

  const handleEvent = useCallback((event: WSEvent) => {
    const d = event.data as Record<string, unknown>

    switch (event.type) {
      case 'new_message': {
        const name = (d.lead_name as string) || 'un lead'
        setStatus('receiving')
        setLabel('Mensaje recibido')
        setDetail(name)
        setEventCount((c) => c + 1)
        // Don't reset — wait for typing/ai_response to follow
        scheduleReset(8_000)
        break
      }
      case 'typing': {
        if (d.is_typing) {
          setStatus('thinking')
          setLabel('Sofía está respondiendo')
          setDetail('')
          if (resetTimerRef.current) clearTimeout(resetTimerRef.current)
        } else {
          scheduleReset(4_000)
        }
        break
      }
      case 'ai_response': {
        setStatus('responded')
        setLabel('Respuesta enviada')
        setDetail('')
        setEventCount((c) => c + 1)
        scheduleReset(4_000)
        break
      }
      case 'stage_changed': {
        const stageName = STAGE_LABELS[(d.new_stage as string) || ''] || (d.new_stage as string) || ''
        const name = (d.lead_name as string) || ''
        setStatus('stage_change')
        setLabel('Lead avanzó de etapa')
        setDetail(stageName ? `${name ? name + ' → ' : ''}${stageName}` : name)
        setEventCount((c) => c + 1)
        scheduleReset(6_000)
        break
      }
      case 'lead_hot': {
        const name = (d.lead_name as string) || 'lead'
        setStatus('hot_lead')
        setLabel('Lead caliente')
        setDetail(name)
        setEventCount((c) => c + 1)
        scheduleReset(6_000)
        break
      }
    }
  }, [scheduleReset])

  useWebSocketEvent(handleEvent)

  // Rotate idle message every 8s when idle
  useEffect(() => {
    if (status !== 'idle') return
    const t = setInterval(() => {
      idleIndexRef.current = (idleIndexRef.current + 1) % IDLE_MESSAGES.length
      setLabel(IDLE_MESSAGES[idleIndexRef.current])
    }, 8_000)
    return () => clearInterval(t)
  }, [status])

  useEffect(() => () => {
    if (resetTimerRef.current) clearTimeout(resetTimerRef.current)
  }, [])

  return { status, label, detail, eventCount }
}
