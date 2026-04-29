import { useCallback, useEffect, useRef, useState } from 'react'
import { openViolationStream, SEVERITY_RANK, Violation } from '../api/violations'
import { useToast } from '../components/ToastProvider'

interface UseViolationStreamResult {
  violations: Violation[]
  unreadCount: number
  markAllRead: () => void
  connected: boolean
}

const BACKOFF_SCHEDULE = [1000, 2000, 4000, 8000, 16000]

export function useViolationStream(): UseViolationStreamResult {
  const [violations, setViolations] = useState<Violation[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [connected, setConnected] = useState(false)
  const { push } = useToast()

  const esRef = useRef<EventSource | null>(null)
  const retryRef = useRef(0)
  const retryTimerRef = useRef<number | null>(null)
  const closedRef = useRef(false)

  const markAllRead = useCallback(() => setUnreadCount(0), [])

  useEffect(() => {
    closedRef.current = false

    const connect = () => {
      if (closedRef.current) return
      let es: EventSource
      try {
        es = openViolationStream()
      } catch {
        scheduleReconnect()
        return
      }
      esRef.current = es

      es.addEventListener('open', () => {
        setConnected(true)
        retryRef.current = 0
      })

      es.addEventListener('init', (ev: MessageEvent) => {
        try {
          const data = JSON.parse(ev.data) as Violation[]
          setViolations(Array.isArray(data) ? data : [])
        } catch {
          // ignore malformed payload
        }
      })

      es.addEventListener('violation', (ev: MessageEvent) => {
        try {
          const v = JSON.parse(ev.data) as Violation
          if (!v || !v.violation_id) return
          setViolations(prev => {
            // De-dupe by violation_id
            if (prev.some(p => p.violation_id === v.violation_id)) return prev
            return [v, ...prev]
          })
          setUnreadCount(c => c + 1)
          if (SEVERITY_RANK[v.severity] >= SEVERITY_RANK.high) {
            push({
              title: `${v.severity.toUpperCase()}: ${v.guardrail_name}`,
              body: v.reason?.slice(0, 140) || `Agent ${v.agent_id} flagged`,
              severity: v.severity,
              violationId: v.violation_id,
            })
          }
        } catch {
          // ignore malformed payload
        }
      })

      es.addEventListener('error', () => {
        setConnected(false)
        try { es.close() } catch { /* noop */ }
        esRef.current = null
        scheduleReconnect()
      })
    }

    const scheduleReconnect = () => {
      if (closedRef.current) return
      const delay = BACKOFF_SCHEDULE[Math.min(retryRef.current, BACKOFF_SCHEDULE.length - 1)]
      retryRef.current += 1
      retryTimerRef.current = window.setTimeout(connect, delay)
    }

    connect()

    return () => {
      closedRef.current = true
      if (retryTimerRef.current) {
        window.clearTimeout(retryTimerRef.current)
        retryTimerRef.current = null
      }
      if (esRef.current) {
        try { esRef.current.close() } catch { /* noop */ }
        esRef.current = null
      }
      setConnected(false)
    }
  }, [push])

  return { violations, unreadCount, markAllRead, connected }
}

export default useViolationStream
