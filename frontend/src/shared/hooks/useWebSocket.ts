import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '@/features/auth'

export type WSEventType =
  | 'new_message'
  | 'stage_changed'
  | 'lead_assigned'
  | 'lead_hot'
  | 'typing'
  | 'ai_response'

export interface WSEvent<T = unknown> {
  type: WSEventType
  data: T
}

interface UseWebSocketOptions {
  /** Called on each parsed message */
  onMessage: (event: WSEvent) => void
  /** Whether to connect at all */
  enabled?: boolean
}

const BASE_WS_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace(/^http/, 'ws')

const MAX_BACKOFF_MS = 30_000

export function useWebSocket({ onMessage, enabled = true }: UseWebSocketOptions) {
  const user = useAuthStore((s) => s.user)
  const wsRef = useRef<WebSocket | null>(null)
  const attemptRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Stable ref for the callback so reconnect never captures a stale version
  const onMessageRef = useRef(onMessage)
  useEffect(() => { onMessageRef.current = onMessage })

  const connect = useCallback(() => {
    if (!user?.broker_id || !enabled) return

    const token = localStorage.getItem('token')
    const userId = String(user.id ?? 'dashboard')
    // Backend endpoint: /ws/{broker_id}/{user_id}
    // Auth: send {"token": "..."} as the first message after connecting
    const url = `${BASE_WS_URL}/ws/${user.broker_id}/${userId}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      attemptRef.current = 0
      // Send token as first message per the backend protocol
      if (token) {
        ws.send(JSON.stringify({ token }))
      }
    }

    ws.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data) as WSEvent
        // Ignore handshake / heartbeat frames
        if ((parsed as any).event === 'connected' || (parsed as any).event === 'ping') return
        // Backend broadcasts with {event, data} shape; normalise to {type, data}
        const normalised: WSEvent = (parsed as any).event
          ? { type: (parsed as any).event as WSEventType, data: (parsed as any).data }
          : parsed
        onMessageRef.current(normalised)
      } catch {
        // ignore malformed frames
      }
    }

    ws.onclose = () => {
      if (!enabled) return
      // Exponential backoff: 1s, 2s, 4s, 8s … capped at 30s
      const delay = Math.min(1000 * 2 ** attemptRef.current, MAX_BACKOFF_MS)
      attemptRef.current += 1
      timerRef.current = setTimeout(connect, delay)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [user?.broker_id, user?.id, enabled])

  useEffect(() => {
    if (!enabled || !user?.broker_id) return
    connect()
    return () => {
      timerRef.current && clearTimeout(timerRef.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [connect, enabled, user?.broker_id])
}
