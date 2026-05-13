import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Drawer, { DrawerClose } from './shared/Drawer'
import {
  GuardrailDecision,
  GuardrailInvocation,
  GuardrailRegistration,
  fetchGuardrailInvocations,
} from '../api/guardrails'

interface Props {
  guardrail: GuardrailRegistration | null
  onClose: () => void
}

function formatTime(iso: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function formatRelative(iso: string): string {
  if (!iso) return '—'
  const ms = Date.now() - new Date(iso).getTime()
  if (Number.isNaN(ms)) return '—'
  if (ms < 60_000) return 'just now'
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`
  return `${Math.floor(ms / 86_400_000)}d ago`
}

function decisionLabel(d: GuardrailDecision): string {
  return d === 'pass' ? 'Pass' : d === 'fail' ? 'Fail' : 'Error'
}

function prettyTiming(t: string): string {
  if (!t) return ''
  return t.replace('_', ' ')
}

function tryPrettyJson(raw: string): string {
  if (!raw) return ''
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

export default function GuardrailDetailDrawer({ guardrail: g, onClose }: Props) {
  const [copied, setCopied] = useState(false)

  // Recent invocations — loaded on drawer open.
  const [invocations, setInvocations] = useState<GuardrailInvocation[]>([])
  const [invocationsLoading, setInvocationsLoading] = useState(false)
  const [invocationsError, setInvocationsError] = useState<string | null>(null)
  // Per-row expansion: which span_ids have evidence/response panes visible.
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!g) {
      setInvocations([])
      setInvocationsError(null)
      setExpanded(new Set())
      return
    }
    let cancelled = false
    setInvocationsLoading(true)
    setInvocationsError(null)
    fetchGuardrailInvocations(g.agent_id, g.guardrail_name, 50)
      .then((rows) => { if (!cancelled) setInvocations(rows) })
      .catch((e) => { if (!cancelled) setInvocationsError(e.message || 'Failed to load invocations') })
      .finally(() => { if (!cancelled) setInvocationsLoading(false) })
    return () => { cancelled = true }
  }, [g])

  const toggleExpand = (spanId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(spanId)) next.delete(spanId)
      else next.add(spanId)
      return next
    })
  }

  const copyPrompt = () => {
    if (!g?.judge_prompt) return
    navigator.clipboard.writeText(g.judge_prompt).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    })
  }

  return (
    <Drawer
      open={!!g}
      onClose={onClose}
      ariaLabel="Guardrail details"
      tone={g?.severity ?? 'neutral'}
      widthPx={680}
    >
      {g && (
        <>
          <header className="drawer-head">
            <div className="drawer-title-row">
              <div>
                <div className="drawer-eyebrow">
                  {g.severity.toUpperCase()} · {g.timing.replace('_', ' ')}
                </div>
                <h3 className="drawer-title mono">{g.guardrail_name}</h3>
              </div>
              <DrawerClose onClose={onClose} />
            </div>
            <div className="drawer-meta-row">
              <span className={`guardrail-chip mode-${g.mode}`}>
                {g.mode === 'monitoring' ? 'Monitoring' : 'Blocking'}
              </span>
              <span className={`guardrail-chip health-${g.health}`}>
                <span className={`guardrail-health-dot dot-${g.health}`} aria-hidden="true" />
                {g.health === 'active' ? 'Active' : g.health === 'error' ? 'Error' : 'Disabled'}
              </span>
              <span className={`guardrail-chip${g.recent_activity_24h > 0 ? ' is-warn' : ''}`}>
                {g.recent_activity_24h} in 24h
              </span>
            </div>
          </header>

          <div className="drawer-body">
            {g.description && (
              <section className="drawer-section">
                <h4>Description</h4>
                <p className="guardrail-detail-desc">{g.description}</p>
              </section>
            )}

            <section className="drawer-section">
              <h4>Configuration</h4>
              <dl className="kv-list">
                <div className="kv-row">
                  <dt>Agent</dt>
                  <dd className="mono">{g.agent_id}</dd>
                </div>
                <div className="kv-row">
                  <dt>Judge model</dt>
                  <dd className="mono">{g.judge_model || '—'}</dd>
                </div>
                <div className="kv-row">
                  <dt>Timing</dt>
                  <dd>{g.timing.replace('_', ' ')}</dd>
                </div>
                <div className="kv-row">
                  <dt>Mode</dt>
                  <dd>{g.mode}</dd>
                </div>
                <div className="kv-row">
                  <dt>Severity</dt>
                  <dd>{g.severity}</dd>
                </div>
                <div className="kv-row">
                  <dt>Health</dt>
                  <dd>
                    {g.health}
                    {g.health_reason && (
                      <span className="text-muted"> · {g.health_reason}</span>
                    )}
                  </dd>
                </div>
                <div className="kv-row">
                  <dt>Registered</dt>
                  <dd>{formatTime(g.registered_at)}</dd>
                </div>
                <div className="kv-row">
                  <dt>Last seen</dt>
                  <dd>{formatTime(g.last_seen_at)}</dd>
                </div>
              </dl>
            </section>

            <section className="drawer-section">
              <div className="prompt-pane-actions">
                <h4 style={{ margin: 0 }}>Recent invocations</h4>
                <span className="text-muted">
                  {invocationsLoading ? 'Loading…' : `${invocations.length} shown`}
                </span>
              </div>

              {invocationsError ? (
                <div className="empty-pane">
                  <p>Failed to load: {invocationsError}</p>
                </div>
              ) : invocationsLoading ? (
                <div className="invocations-list">
                  {[...Array(3)].map((_, i) => (
                    <div key={i} className="loading-skeleton" style={{ height: 56, marginBottom: 8 }} />
                  ))}
                </div>
              ) : invocations.length === 0 ? (
                <div className="empty-pane">
                  <p>No invocations recorded yet for this guardrail.</p>
                  <p className="text-muted">
                    Spans appear here as soon as the SDK exports them. If you just
                    enabled the guardrail, run an agent and refresh in a few seconds.
                  </p>
                </div>
              ) : (
                <ul className="invocations-list" role="list">
                  {invocations.map((inv) => {
                    const isOpen = expanded.has(inv.span_id)
                    const hasDetails = !!(inv.evidence || inv.response_json)
                    // For rows with no extra detail (typical 'pass' with no
                    // evidence), render as a non-interactive div instead of
                    // a disabled button — the content (decision, reason,
                    // timestamp) is still readable by screen readers, and
                    // we don't surface a "this is disabled, ignore it" hint
                    // that's actively misleading.
                    const headInner = (
                      <>
                        <span className={`invocation-decision deci-${inv.decision}`}>
                          {decisionLabel(inv.decision)}
                        </span>
                        {inv.timing && (
                          <span className="invocation-phase">{prettyTiming(inv.timing)}</span>
                        )}
                        <span className="invocation-reason" title={inv.reason}>
                          {inv.reason || (inv.decision === 'pass' ? 'No flags' : 'No reason recorded')}
                        </span>
                        <span className="invocation-time text-muted">
                          {formatRelative(inv.observed_at)}
                        </span>
                      </>
                    )
                    return (
                      <li key={inv.span_id} className="invocation-row">
                        {hasDetails ? (
                          <button
                            type="button"
                            className="invocation-row-head"
                            onClick={() => toggleExpand(inv.span_id)}
                            aria-expanded={isOpen}
                          >
                            {headInner}
                          </button>
                        ) : (
                          <div className="invocation-row-head invocation-row-head--static">
                            {headInner}
                          </div>
                        )}

                        {isOpen && hasDetails && (
                          <div className="invocation-row-body">
                            {inv.evidence && (
                              <div className="invocation-section">
                                <div className="invocation-section-head">
                                  <span className="invocation-section-label">Evidence (input checked)</span>
                                </div>
                                <pre className="invocation-pre">{inv.evidence}</pre>
                              </div>
                            )}
                            {inv.response_json && (
                              <div className="invocation-section">
                                <div className="invocation-section-head">
                                  <span className="invocation-section-label">
                                    Provider response ({inv.provider})
                                  </span>
                                </div>
                                <pre className="invocation-pre mono">{tryPrettyJson(inv.response_json)}</pre>
                              </div>
                            )}
                            <div className="invocation-section">
                              <Link
                                to={`/sessions/${inv.trace_id}`}
                                className="btn btn-sm btn-ghost"
                                onClick={onClose}
                              >
                                View full trace →
                              </Link>
                            </div>
                          </div>
                        )}
                      </li>
                    )
                  })}
                </ul>
              )}
            </section>

            <section className="drawer-section">
              <div className="prompt-pane-actions">
                <h4 style={{ margin: 0 }}>Judge prompt</h4>
                {g.judge_prompt && (
                  <button className="btn btn-sm btn-ghost" onClick={copyPrompt}>
                    {copied ? '✓ Copied' : 'Copy prompt'}
                  </button>
                )}
              </div>
              {g.judge_prompt ? (
                <pre className="prompt-pane-body">{g.judge_prompt}</pre>
              ) : (
                <div className="empty-pane">
                  <p>No prompt recorded for this guardrail.</p>
                  <p className="text-muted">
                    SDK versions before MVP 4.5 didn&apos;t emit the prompt with the
                    registration span. Re-register the guardrail with the latest
                    SDK to populate this field. Protector Plus guardrails don&apos;t
                    have a local prompt — the judge runs server-side.
                  </p>
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </Drawer>
  )
}
