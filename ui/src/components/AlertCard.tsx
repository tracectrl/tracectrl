import { forwardRef } from 'react'
import { Link } from 'react-router-dom'
import type { Violation } from '../api/violations'

interface Props {
  violation: Violation
  highlighted?: boolean
  onViewEvidence: (v: Violation) => void
  onMarkResolved?: (v: Violation) => void
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return '—'
    // Clamp negatives in case of clock skew between SDK host (where the span
    // was emitted) and the user's machine — "−12s ago" looks broken.
    const diffSec = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000))
    if (diffSec < 60) return `${diffSec}s ago`
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
    // Older than a day — short calendar form, not the noisy full ISO.
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  } catch {
    return '—'
  }
}

const AlertCard = forwardRef<HTMLDivElement, Props>(function AlertCard(
  { violation, highlighted, onViewEvidence, onMarkResolved },
  ref,
) {
  const { severity, guardrail_name, reason, agent_id, trace_id, observed_at, decision } = violation

  return (
    <div
      ref={ref}
      className={`alert-card alert-card-${severity}${highlighted ? ' alert-card-highlight' : ''}`}
      data-violation-id={violation.violation_id}
    >
      <div className="alert-card-head">
        <span className={`alert-card-severity sev-${severity}`}>{severity.toUpperCase()}</span>
        <span className="alert-card-guardrail">{guardrail_name}</span>
        <span className={`alert-card-decision decision-${decision}`}>{decision}</span>
        <span className="alert-card-time">{formatTime(observed_at)}</span>
      </div>

      <div className="alert-card-reason">{reason || <em className="muted">(no reason)</em>}</div>

      <div className="alert-card-meta">
        <span className="alert-card-meta-item">
          <span className="alert-card-meta-label">Agent</span>
          <span className="alert-card-meta-value mono">{agent_id}</span>
        </span>
        <span className="alert-card-meta-item">
          <span className="alert-card-meta-label">Session</span>
          <Link to={`/sessions/${trace_id}`} className="alert-card-meta-link mono">
            {trace_id.slice(0, 12)}…
          </Link>
        </span>
        <span className="alert-card-meta-item">
          <span className="alert-card-meta-label">Judge</span>
          <span className="alert-card-meta-value mono">{violation.judge_model}</span>
        </span>
      </div>

      <div className="alert-card-actions">
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => onViewEvidence(violation)}
        >
          View evidence
        </button>
        {onMarkResolved && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => onMarkResolved(violation)}
          >
            Mark resolved
          </button>
        )}
      </div>
    </div>
  )
})

export default AlertCard
