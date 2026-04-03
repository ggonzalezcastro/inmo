/**
 * Singleton WebSocket context.
 * One connection per session, shared across all components.
 * Components subscribe via useWebSocketEvent() instead of opening their own WS.
 */
import { createContext, useContext, useEffect, useRef, useCallback, useState } from 'react'
import type { ReactNode } from 'react'
import { useAuthStore } from '@/features/auth'
import type { WSEvent, WSEventType } from '@/shared/hooks/useWebSocket'
export type { WSEvent, WSEventType }

type Listener = (event: WSEvent) => void

interface WSContextValue {
  subscribe: (fn: Listener) => () => void
  connected: boolean
}

const WebSocketContext = createContext<WSContextValue | null>(null)

const BASE_WS_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000')
  .replace(/^http/, 'ws')

const MAX_BACKOFF_MS = 30_000

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const user = useAuthStore((s) => s.user)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const listenersRef = useRef<Set<Listener>>(new Set())
  const attemptRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const enabledRef = useRef(true)

  const subscribe = useCallback((fn: Listener) => {
    listenersRef.current.add(fn)
    return () => { listenersRef.current.delete(fn) }
  }, [])

  const connect = useCallback(() => {
    if (!enabledRef.current || !user?.broker_id) return
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return

    const token = localStorage.getItem('token')
    const userId = String(user.id ?? 'dashboard')
    const url = `${BASE_WS_URL}/ws/${user.broker_id}/${userId}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      attemptRef.current = 0
      setConnected(true)
      if (token) ws.send(JSON.stringify({ token }))
    }

    ws.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data) as WSEvent
        if ((parsed as any).event === 'connected' || (parsed as any).event === 'ping') return
        const normalised: WSEvent = (parsed as any).event
          ? { type: (parsed as any).event as WSEventType, data: (parsed as any).data }
          : parsed
        listenersRef.current.forEach((fn) => fn(normalised))
      } catch {
        // ignore malformed frames
      }
    }

    ws.onclose = (e) => {
      setConnected(false)
      if (!enabledRef.current) return
      if (e.code === 4001) return
      const delay = Math.min(1000 * 2 ** attemptRef.current, MAX_BACKOFF_MS)
      attemptRef.current += 1
      timerRef.current = setTimeout(connect, delay)
    }

    ws.onerror = () => ws.close()
  }, [user?.broker_id, user?.id])

  useEffect(() => {
    if (!user?.broker_id) return
    enabledRef.current = true
    connect()
    return () => {
      enabledRef.current = false
      timerRef.current && clearTimeout(timerRef.current)
      wsRef.current?.close()
      wsRef.current = null
      listenersRef.current.clear() // Prevent stale subscriptions after broker change/logout
    }
  }, [connect, user?.broker_id])

  return (
    <WebSocketContext.Provider value={{ subscribe, connected }}>
      {children}
    </WebSocketContext.Provider>
  )
}

export function useWebSocketEvent(onMessage: Listener, enabled = true) {
  const ctx = useContext(WebSocketContext)
  const onMessageRef = useRef(onMessage)
  useEffect(() => { onMessageRef.current = onMessage })

  useEffect(() => {
    if (!ctx || !enabled) return
    return ctx.subscribe((event) => onMessageRef.current(event))
  }, [ctx, enabled])
}
