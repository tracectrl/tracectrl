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
    <div className={`toast toast-${severity} toast-${phase}`} role="status">
      <span className="toast-accent" aria-hidden="true" />
      <button
        type="button"
        className="toast-body-button"
        onClick={onClick}
        aria-label={title}
      >
        <div className="toast-content">
          <div className="toast-title">{title}</div>
          {body && <div className="toast-body">{body}</div>}
        </div>
      </button>
      {onDismiss && (
        <button
          type="button"
          className="toast-dismiss"
          onClick={onDismiss}
          aria-label="Dismiss notification"
        >
          ×
        </button>
      )}
    </div>
  )
}

export { ToastProvider, useToast } from './ToastProvider'
export type { ToastInput } from './ToastProvider'
