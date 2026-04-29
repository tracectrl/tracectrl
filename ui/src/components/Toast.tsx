import type { Severity } from '../api/violations'

export interface ToastProps {
  id: string
  title: string
  body?: string
  severity?: Severity | 'neutral'
  phase?: 'enter' | 'visible' | 'exit'
  onClick?: () => void
  onDismiss?: () => void
}

/**
 * Presentational single-toast component. The global stack and animation
 * state machine lives in <ToastProvider>; this component is rendered there
 * but is exported for direct use / testing.
 */
export default function Toast({
  title,
  body,
  severity = 'neutral',
  phase = 'visible',
  onClick,
  onDismiss,
}: ToastProps) {
  return (
    <button
      type="button"
      className={`toast toast-${severity} toast-${phase}`}
      onClick={onClick}
    >
      <span className="toast-accent" aria-hidden="true" />
      <div className="toast-content">
        <div className="toast-title">{title}</div>
        {body && <div className="toast-body">{body}</div>}
      </div>
      {onDismiss && (
        <span
          className="toast-dismiss"
          role="presentation"
          onClick={e => { e.stopPropagation(); onDismiss() }}
          aria-label="Dismiss"
        >
          ×
        </span>
      )}
    </button>
  )
}

export { ToastProvider, useToast } from './ToastProvider'
export type { ToastInput } from './ToastProvider'
