import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import AlertCard from '../components/AlertCard'
import Drawer, { DrawerClose } from '../components/shared/Drawer'
import EmptyState from '../components/shared/EmptyState'
import { useViolationsContext } from '../context/ViolationsContext'
import type { Severity, Violation } from '../api/violations'

const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low']

export default function Alerts() {
  const { violations, markAllRead } = useViolationsContext()
  const [searchParams, setSearchParams] = useSearchParams()
  const focusId = searchParams.get('focus')

  const [activeSeverities, setActiveSeverities] = useState<Set<Severity>>(new Set())
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set())
  const [drawerViolation, setDrawerViolation] = useState<Violation | null>(null)
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map())

  // Mark all read whenever the page is visited
  useEffect(() => {
    markAllRead()
  }, [markAllRead])

  // Scroll to focused alert
  useEffect(() => {
    if (!focusId) return
    const el = cardRefs.current.get(focusId)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [focusId, violations])

  const toggleSeverity = (s: Severity) => {
    setActiveSeverities(prev => {
      const next = new Set(prev)
      if (next.has(s)) next.delete(s)
      else next.add(s)
      return next
    })
  }

  const filtered = useMemo(() => {
    return violations.filter(v => {
      if (resolvedIds.has(v.violation_id)) return false
      if (activeSeverities.size === 0) return true
      return activeSeverities.has(v.severity)
    })
  }, [violations, activeSeverities, resolvedIds])

  const handleMarkResolved = (v: Violation) => {
    setResolvedIds(prev => {
      const next = new Set(prev)
      next.add(v.violation_id)
      return next
    })
  }

  const handleViewEvidence = (v: Violation) => setDrawerViolation(v)

  const clearFocus = () => {
    if (focusId) {
      const next = new URLSearchParams(searchParams)
      next.delete('focus')
      setSearchParams(next, { replace: true })
    }
  }

  const totalCount = violations.length

  return (
    <div className="alerts-page">
      <header className="alerts-header">
        <div>
          <h2 style={{ margin: 0 }}>Alerts</h2>
          <p className="alerts-subtitle">
            {totalCount} {totalCount === 1 ? 'violation' : 'violations'}
            {filtered.length !== totalCount && ` · ${filtered.length} shown`}
          </p>
        </div>
        <div className="alerts-header-actions">
          <button type="button" className="btn btn-ghost btn-sm" onClick={markAllRead}>
            Mark all read
          </button>
        </div>
      </header>

      <div className="alerts-filters" role="toolbar" aria-label="Filter by severity">
        <button
          type="button"
          className={`chip${activeSeverities.size === 0 ? ' chip-active' : ''}`}
          onClick={() => setActiveSeverities(new Set())}
        >
          All
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

      <div className="alerts-list">
        {filtered.length === 0 ? (
          <EmptyState
            title={totalCount === 0 ? 'No alerts — your agents are clean' : 'No alerts match this filter'}
            hint={totalCount === 0 ? 'New violations will appear here in real time.' : 'Try clearing severity filters.'}
          />
        ) : (
          filtered.map(v => (
            <AlertCard
              key={v.violation_id}
              violation={v}
              highlighted={focusId === v.violation_id}
              onViewEvidence={handleViewEvidence}
              onMarkResolved={handleMarkResolved}
              ref={el => {
                if (el) cardRefs.current.set(v.violation_id, el)
                else cardRefs.current.delete(v.violation_id)
              }}
            />
          ))
        )}
      </div>

      <Drawer
        open={drawerViolation !== null}
        onClose={() => { setDrawerViolation(null); clearFocus() }}
        ariaLabel="Violation evidence"
        tone={drawerViolation?.severity ?? 'neutral'}
        widthPx={520}
      >
        {drawerViolation && (
          <>
            <header className="drawer-header">
              <div>
                <div className="drawer-eyebrow">{drawerViolation.severity.toUpperCase()} · {drawerViolation.guardrail_name}</div>
                <h3 style={{ margin: '4px 0 0' }}>Violation evidence</h3>
              </div>
              <div style={{ marginLeft: 'auto' }}>
                <DrawerClose onClose={() => { setDrawerViolation(null); clearFocus() }} />
              </div>
            </header>

            <div className="drawer-body">
              <section className="drawer-section">
                <h4>Reason</h4>
                <p className="alerts-reason-text">{drawerViolation.reason || '—'}</p>
              </section>

              <section className="drawer-section">
                <h4>Evidence</h4>
                <pre className="alerts-evidence-block">
                  {prettyEvidence(drawerViolation.evidence)}
                </pre>
              </section>

              <section className="drawer-section">
                <h4>Context</h4>
                <div className="kv-list">
                  <div className="kv-item">
                    <div className="kv-key">Agent</div>
                    <div className="kv-value mono">{drawerViolation.agent_id}</div>
                  </div>
                  <div className="kv-item">
                    <div className="kv-key">Judge model</div>
                    <div className="kv-value mono">{drawerViolation.judge_model}</div>
                  </div>
                  <div className="kv-item">
                    <div className="kv-key">Decision</div>
                    <div className="kv-value mono">{drawerViolation.decision}</div>
                  </div>
                  <div className="kv-item">
                    <div className="kv-key">Observed</div>
                    <div className="kv-value mono">{drawerViolation.observed_at}</div>
                  </div>
                  <div className="kv-item">
                    <div className="kv-key">Trace ID</div>
                    <div className="kv-value mono">{drawerViolation.trace_id}</div>
                  </div>
                  <div className="kv-item">
                    <div className="kv-key">Span ID</div>
                    <div className="kv-value mono">{drawerViolation.span_id}</div>
                  </div>
                </div>
              </section>

              <div className="drawer-actions">
                <Link
                  to={`/sessions/${drawerViolation.trace_id}`}
                  className="btn btn-primary btn-sm"
                  onClick={() => setDrawerViolation(null)}
                >
                  Open trace
                </Link>
              </div>
            </div>
          </>
        )}
      </Drawer>
    </div>
  )
}

function prettyEvidence(raw: string): string {
  if (!raw) return '—'
  try {
    const parsed = JSON.parse(raw)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return raw
  }
}
