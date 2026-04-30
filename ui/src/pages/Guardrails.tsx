import { useEffect, useMemo, useState, useCallback } from 'react'
import { fetchGuardrails, GuardrailRegistration, GuardrailSeverity } from '../api/guardrails'
import GuardrailCard from '../components/GuardrailCard'
import GuardrailDetailDrawer from '../components/GuardrailDetailDrawer'
import EmptyState from '../components/shared/EmptyState'
import ErrorBanner from '../components/shared/ErrorBanner'

const SEVERITIES: GuardrailSeverity[] = ['critical', 'high', 'medium', 'low']
const POLL_INTERVAL_MS = 30_000

export default function Guardrails() {
  const [guardrails, setGuardrails] = useState<GuardrailRegistration[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeSeverities, setActiveSeverities] = useState<Set<GuardrailSeverity>>(new Set())
  const [selected, setSelected] = useState<GuardrailRegistration | null>(null)

  useEffect(() => { document.title = 'Guardrails — TraceCtrl' }, [])

  const load = useCallback((isInitial: boolean) => {
    if (isInitial) setLoading(true)
    fetchGuardrails()
      .then(data => {
        setGuardrails(data)
        setError(null)
      })
      .catch(err => {
        // Graceful: keep last data; surface error banner
        setError(err.message || 'Failed to load guardrails')
        if (isInitial) setGuardrails([])
      })
      .finally(() => {
        if (isInitial) setLoading(false)
      })
  }, [])

  useEffect(() => {
    load(true)
    const id = window.setInterval(() => load(false), POLL_INTERVAL_MS)
    return () => window.clearInterval(id)
  }, [load])

  const toggleSeverity = (s: GuardrailSeverity) => {
    setActiveSeverities(prev => {
      const next = new Set(prev)
      if (next.has(s)) next.delete(s)
      else next.add(s)
      return next
    })
  }

  const filtered = useMemo(() => {
    if (activeSeverities.size === 0) return guardrails
    return guardrails.filter(g => activeSeverities.has(g.severity))
  }, [guardrails, activeSeverities])

  const grouped = useMemo(() => {
    const buckets = new Map<string, GuardrailRegistration[]>()
    for (const g of filtered) {
      const arr = buckets.get(g.agent_id) ?? []
      arr.push(g)
      buckets.set(g.agent_id, arr)
    }
    return [...buckets.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [filtered])

  const totalCount = guardrails.length
  const activeCount = guardrails.filter(g => g.health === 'active').length
  const violatingCount = guardrails.filter(g => g.recent_activity_24h > 0).length

  return (
    <div className="guardrails-page">
      <div className="page-header">
        <div className="section-tag">Security</div>
        <h2>Guardrails</h2>
        <p className="page-meta" aria-live="polite">
          {loading
            ? 'Loading guardrails...'
            : `${totalCount} total · ${activeCount} active · ${violatingCount} with violations 24h`}
        </p>
      </div>

      {error && <ErrorBanner error={error} onRetry={() => load(true)} />}

      <div className="guardrails-filters" role="toolbar" aria-label="Filter by severity">
        <button
          type="button"
          className={`chip${activeSeverities.size === 0 ? ' chip-active' : ' chip-clear'}`}
          onClick={() => setActiveSeverities(new Set())}
        >
          {activeSeverities.size === 0 ? 'All' : 'Clear filters'}
        </button>
        {SEVERITIES.map(s => (
          <button
            key={s}
            type="button"
            className={`chip chip-${s}${activeSeverities.has(s) ? ' chip-active' : ''}`}
            onClick={() => toggleSeverity(s)}
          >
            {s}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="guardrails-list">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="loading-skeleton" style={{ height: 130, marginBottom: 12 }} />
          ))}
        </div>
      ) : grouped.length === 0 ? (
        <EmptyState
          title={totalCount === 0 ? 'No guardrails registered yet' : 'No guardrails match this filter'}
          hint={
            totalCount === 0
              ? 'Pre-register guardrails via the SDK so they show up here before they ever fire. See the docs for setup.'
              : 'Try clearing severity filters.'
          }
        />
      ) : (
        <div className="guardrails-groups">
          {grouped.map(([agentId, items]) => (
            <section key={agentId} className="guardrails-group">
              <header className="guardrails-group-head">
                <h3 className="guardrails-group-title mono">{agentId}</h3>
                <span className="guardrails-group-count">{items.length}</span>
              </header>
              <div className="guardrails-list">
                {items.map(g => (
                  <GuardrailCard
                    key={`${g.agent_id}/${g.guardrail_name}`}
                    guardrail={g}
                    onClick={setSelected}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      <GuardrailDetailDrawer guardrail={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
