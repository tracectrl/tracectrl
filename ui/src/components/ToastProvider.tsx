import { createContext, ReactNode, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import type { Severity } from '../api/violations'

export interface ToastInput {
  id?: string
  title: string
  body?: string
  severity?: Severity | 'neutral'
  durationMs?: number
  // Optional violation_id — clicking the toast navigates to /alerts?focus=<id>
  violationId?: string
}

interface ToastItem extends Required<Pick<ToastInput, 'title'>> {
  id: string
  body?: string
  severity: Severity | 'neutral'
  durationMs: number
  violationId?: string
  createdAt: number
  // entry/exit phase for animation
  phase: 'enter' | 'visible' | 'exit'
}

interface ToastCtx {
  push: (t: ToastInput) => string
  dismiss: (id: string) => void
}

const ToastContext = createContext<ToastCtx | null>(null)

const MAX_VISIBLE = 5
// 30s with a visible countdown — long enough to read + click without feeling
// rushed, short enough that an unattended demo doesn't pile up old alerts.
const DEFAULT_DURATION = 30000

export function useToast(): ToastCtx {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>')
  return ctx
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const timeoutsRef = useRef<Map<string, number>>(new Map())
  const navigate = useNavigate()

  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.map(t => (t.id === id ? { ...t, phase: 'exit' } : t)))
    // Remove after exit animation (220ms). Also clear the ref entry so
    // future push() with the same id is allowed to recreate the toast.
    const remove = window.setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
      timeoutsRef.current.delete(id)
    }, 240)
    const existing = timeoutsRef.current.get(id)
    if (existing) window.clearTimeout(existing)
    timeoutsRef.current.set(id, remove)
  }, [])

  const push = useCallback((input: ToastInput): string => {
    const id = input.id ?? `toast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    // Hard de-dupe: if a toast with this id is already alive, KEEP it as-is.
    // Don't reset the timer, don't replay the entry animation, don't append.
    // SSE may re-deliver the same violation many times; the first push wins.
    if (timeoutsRef.current.has(id)) {
      return id
    }
    const item: ToastItem = {
      id,
      title: input.title,
      body: input.body,
      severity: input.severity ?? 'neutral',
      durationMs: input.durationMs ?? DEFAULT_DURATION,
      violationId: input.violationId,
      createdAt: Date.now(),
      phase: 'enter',
    }
    setToasts(prev => {
      // Belt-and-suspenders: if state somehow has it but timer doesn't, drop
      // the stale entry first.
      const filtered = prev.filter(t => t.id !== id)
      const next = [item, ...filtered]
      if (next.length > MAX_VISIBLE) return next.slice(0, MAX_VISIBLE)
      return next
    })
    // Promote enter -> visible on next tick to trigger CSS transition
    window.setTimeout(() => {
      setToasts(prev => prev.map(t => (t.id === id ? { ...t, phase: 'visible' } : t)))
    }, 20)
    // Auto-dismiss
    const dismissTimer = window.setTimeout(() => dismiss(id), item.durationMs)
    timeoutsRef.current.set(id, dismissTimer)
    return id
  }, [dismiss])

  // Cleanup timeouts on unmount
  useEffect(() => {
    const map = timeoutsRef.current
    return () => {
      map.forEach(t => window.clearTimeout(t))
      map.clear()
    }
  }, [])

  const handleClick = useCallback((t: ToastItem) => {
    if (t.violationId) {
      navigate(`/alerts?focus=${encodeURIComponent(t.violationId)}`)
    }
    dismiss(t.id)
  }, [navigate, dismiss])

  return (
    <ToastContext.Provider value={{ push, dismiss }}>
      {children}
      {createPortal(
        <div className="toast-container" role="region" aria-label="Notifications" aria-live="polite">
          {toasts.map(t => (
            <div
              key={t.id}
              className={`toast toast-${t.severity} toast-${t.phase}`}
              role="status"
              style={{ ['--toast-duration' as string]: `${t.durationMs}ms` }}
            >
              <span className="toast-accent" aria-hidden="true" />
              <button
                type="button"
                className="toast-body-button"
                onClick={() => handleClick(t)}
                aria-label={t.violationId ? `Open ${t.title} in alerts` : t.title}
              >
                <div className="toast-content">
                  <div className="toast-title">{t.title}</div>
                  {t.body && <div className="toast-body">{t.body}</div>}
                </div>
              </button>
              <button
                type="button"
                className="toast-dismiss"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss notification"
              >
                ×
              </button>
              {/* Auto-dismiss countdown — drains from 100% to 0% over the
                  toast's lifetime, paused on hover so users have time to
                  read/click without losing it. */}
              <span className="toast-countdown" aria-hidden="true" />
            </div>
          ))}
        </div>,
        document.body
      )}
    </ToastContext.Provider>
  )
}

export default ToastProvider
