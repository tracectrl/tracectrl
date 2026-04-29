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
const DEFAULT_DURATION = 8000

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
    // Remove after exit animation (220ms)
    const remove = window.setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 240)
    const existing = timeoutsRef.current.get(id)
    if (existing) window.clearTimeout(existing)
    timeoutsRef.current.set(id, remove)
  }, [])

  const push = useCallback((input: ToastInput): string => {
    const id = input.id ?? `toast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
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
      const next = [item, ...prev]
      // Cap at MAX_VISIBLE — overflow toasts dismissed immediately
      if (next.length > MAX_VISIBLE) {
        const trimmed = next.slice(0, MAX_VISIBLE)
        return trimmed
      }
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
            <button
              key={t.id}
              type="button"
              className={`toast toast-${t.severity} toast-${t.phase}`}
              onClick={() => handleClick(t)}
            >
              <span className="toast-accent" aria-hidden="true" />
              <div className="toast-content">
                <div className="toast-title">{t.title}</div>
                {t.body && <div className="toast-body">{t.body}</div>}
              </div>
              <span
                className="toast-dismiss"
                role="presentation"
                onClick={e => { e.stopPropagation(); dismiss(t.id) }}
                aria-label="Dismiss"
              >
                ×
              </span>
            </button>
          ))}
        </div>,
        document.body
      )}
    </ToastContext.Provider>
  )
}

export default ToastProvider
