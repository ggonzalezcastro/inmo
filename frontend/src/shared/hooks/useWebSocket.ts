import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '@/features/auth'

export type WSEventType =
  | 'new_message'
  | 'stage_changed'
  | 'lead_assigned'
  | 'lead_hot'
  | 'typing'

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
  const brokerId = useAuthStore((s) => s.user?.broker_id)
  const wsRef = useRef<WebSocket | null>(null)
  const attemptRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Stable ref for the callback so reconnect never captures a stale version
  const onMessageRef = useRef(onMessage)
  useEffect(() => { onMessageRef.current = onMessage })

  const connect = useCallback(() => {
    if (!brokerId || !enabled) return

    const token = localStorage.getItem('token')
    const url = `${BASE_WS_URL}/ws/${brokerId}${token ? `?token=${token}` : ''}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data) as WSEvent
        onMessageRef.current(parsed)
      } catch {
        // ignore malformed frames
      }
    }

    ws.onopen = () => {
      attemptRef.current = 0
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
  }, [brokerId, enabled])

  useEffect(() => {
    if (!enabled || !brokerId) return
    connect()
    return () => {
      timerRef.current && clearTimeout(timerRef.current)
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [connect, enabled, brokerId])
}
