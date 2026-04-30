import { useState } from 'react'
import Drawer, { DrawerClose } from './shared/Drawer'
import { GuardrailRegistration } from '../api/guardrails'

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

export default function GuardrailDetailDrawer({ guardrail: g, onClose }: Props) {
  const [copied, setCopied] = useState(false)

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
      widthPx={640}
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
                      <span className="text-muted"> — {g.health_reason}</span>
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
                    SDK versions before MVP 4.5 didn't emit the prompt with the
                    registration span. Re-register the guardrail with the latest
                    SDK to populate this field.
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
