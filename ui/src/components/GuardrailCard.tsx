import { GuardrailRegistration } from '../api/guardrails'

interface Props {
  guardrail: GuardrailRegistration
  onClick?: (g: GuardrailRegistration) => void
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

function truncate(s: string, max = 100): string {
  if (!s) return ''
  if (s.length <= max) return s
  return s.slice(0, max - 1).trimEnd() + '…'
}

function providerLabel(p: string | undefined): string {
  if (p === 'protector_plus') return 'Protector Plus'
  return 'Judge LLM'
}

export default function GuardrailCard({ guardrail: g, onClick }: Props) {
  const severityClass = `guardrail-card-${g.severity}`
  const activityWarn = g.recent_activity_24h > 0
  const interactive = !!onClick
  const provider = g.provider || 'judge_llm'

  return (
    <div
      className={`guardrail-card ${severityClass}${interactive ? ' is-interactive' : ''}`}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-label={interactive ? `Open ${g.guardrail_name} details` : undefined}
      onClick={interactive ? () => onClick!(g) : undefined}
      onKeyDown={interactive ? (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick!(g)
        }
      } : undefined}
    >
      <div className="guardrail-card-head">
        <div className="guardrail-card-name" title={g.guardrail_name}>
          {g.guardrail_name}
        </div>
        <span className={`guardrail-provider-chip guardrail-provider-${provider}`} title={`Provider: ${providerLabel(provider)}`}>
          {providerLabel(provider)}
        </span>
        <span className={`guardrail-sev sev-${g.severity}`}>
          {g.severity.toUpperCase()}
        </span>
      </div>

      {g.description && (
        <p className="guardrail-card-desc" title={g.description}>
          {truncate(g.description, 100)}
        </p>
      )}

      <div className="guardrail-chips">
        <span className={`guardrail-chip guardrail-chip-mode mode-${g.mode}`}>
          <span className="guardrail-chip-icon" aria-hidden="true">⚙</span>
          {g.mode === 'monitoring' ? 'Monitoring' : 'Blocking'}
        </span>
        <span
          className={`guardrail-chip guardrail-chip-health health-${g.health}`}
          title={g.health_reason || g.health}
        >
          <span className={`guardrail-health-dot dot-${g.health}`} aria-hidden="true" />
          {g.health === 'active' ? 'Active' : g.health === 'error' ? 'Error' : 'Disabled'}
        </span>
        <span className={`guardrail-chip guardrail-chip-activity${activityWarn ? ' is-warn' : ''}`}>
          <span className="guardrail-chip-icon" aria-hidden="true">🔔</span>
          {g.recent_activity_24h} in 24h
        </span>
      </div>

      <div className="guardrail-card-foot text-muted">
        <span className="mono">{g.judge_model || '—'}</span>
        <span className="guardrail-card-foot-sep">·</span>
        <span>Registered {formatRelative(g.registered_at)}</span>
      </div>
    </div>
  )
}
