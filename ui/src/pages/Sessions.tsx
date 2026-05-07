import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { fetchSessions, fetchTraceSpans, SessionSummary, SpanDetail, formatDuration } from '../api/sessions'
import TraceTreeView from '../components/TraceTreeView'
import SpanDetailPanel from '../components/SpanDetailPanel'
import SortableTh from '../components/shared/SortableTh'
import EmptyState from '../components/shared/EmptyState'
import ErrorBanner from '../components/shared/ErrorBanner'
import { useProject } from '../context/ProjectContext'

type SortKey = 'start_time' | 'total_duration_ns' | 'span_count' | 'root_span_name'

export default function Sessions() {
  const { selectedProject } = useProject()
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('start_time')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(null)
  const [expandedSpans, setExpandedSpans] = useState<SpanDetail[]>([])
  const [expandedLoading, setExpandedLoading] = useState(false)
  const [expandedError, setExpandedError] = useState<string | null>(null)
  const [selectedSpan, setSelectedSpan] = useState<SpanDetail | null>(null)

  useEffect(() => { document.title = 'Sessions — TraceCtrl' }, [])

  const load = useCallback(() => {
    setError(null)
    setLoading(true)
    fetchSessions(selectedProject)
      .then(setSessions)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedProject])

  useEffect(() => { load() }, [load])

  const sorted = useMemo(() => {
    const copy = [...sessions]
    copy.sort((a, b) => {
      let cmp = 0
      if (sortKey === 'start_time') cmp = a.start_time.localeCompare(b.start_time)
      else if (sortKey === 'total_duration_ns') cmp = a.total_duration_ns - b.total_duration_ns
      else if (sortKey === 'span_count') cmp = a.span_count - b.span_count
      else if (sortKey === 'root_span_name') cmp = (a.root_span_name ?? '').localeCompare(b.root_span_name ?? '')
      return sortDir === 'asc' ? cmp : -cmp
    })
    return copy
  }, [sessions, sortKey, sortDir])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const formatTime = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  }

  const handleRowActivate = useCallback((session: SessionSummary) => {
    const traceId = session.trace_id
    if (expandedTraceId === traceId) {
      setExpandedTraceId(null)
      setExpandedSpans([])
      setSelectedSpan(null)
      return
    }
    setExpandedTraceId(traceId)
    setExpandedLoading(true)
    setExpandedError(null)
    setSelectedSpan(null)
    const allTraceIds = session.extra_trace_ids && session.extra_trace_ids.length > 0
      ? [traceId, ...session.extra_trace_ids]
      : [traceId]
    Promise.all(allTraceIds.map(tid => fetchTraceSpans(tid)))
      .then(results => setExpandedSpans(results.flat()))
      .catch(err => {
        setExpandedSpans([])
        setExpandedError(err instanceof Error ? err.message : 'Failed to load spans')
      })
      .finally(() => setExpandedLoading(false))
  }, [expandedTraceId])

  const handleSpanSelect = useCallback((span: SpanDetail) => {
    setSelectedSpan(span)
  }, [])

  const maxDuration = useMemo(() => {
    if (sessions.length === 0) return 1
    return Math.max(...sessions.map(s => s.total_duration_ns))
  }, [sessions])

  const p95Duration = useMemo(() => {
    if (sessions.length < 4) return Infinity
    const sortedD = [...sessions].map(s => s.total_duration_ns).sort((a, b) => a - b)
    const idx = Math.floor(sortedD.length * 0.95)
    return sortedD[Math.min(idx, sortedD.length - 1)]
  }, [sessions])

  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Monitor</div>
        <h2>Sessions</h2>
        <p className="page-meta" aria-live="polite">
          {loading ? 'Loading sessions...' : `${sessions.length} traces`}
        </p>
      </div>

      {error && <ErrorBanner error={error} onRetry={load} />}

      {loading ? (
        <div className="table-container">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="loading-skeleton" style={{ height: 44, marginBottom: 2 }} />
          ))}
        </div>
      ) : sessions.length === 0 ? (
        <EmptyState
          title="No Sessions Yet"
          hint="Sessions will appear here once your instrumented agents start sending traces via OpenTelemetry."
          icon={
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
          }
        />
      ) : (
        <div className="sessions-list">
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 28 }} />
                  <SortableTh active={sortKey === 'root_span_name'} direction={sortDir} onToggle={() => toggleSort('root_span_name')}>Root Span</SortableTh>
                  <th>Agent</th>
                  <SortableTh active={sortKey === 'span_count'} direction={sortDir} onToggle={() => toggleSort('span_count')}>Spans</SortableTh>
                  <SortableTh active={sortKey === 'total_duration_ns'} direction={sortDir} onToggle={() => toggleSort('total_duration_ns')}>Duration</SortableTh>
                  <th style={{ minWidth: 120 }}>Waterfall</th>
                  <th>Status</th>
                  <SortableTh active={sortKey === 'start_time'} direction={sortDir} onToggle={() => toggleSort('start_time')}>Time</SortableTh>
                </tr>
              </thead>
              <tbody>
                {sorted.map(session => {
                  const isExpanded = expandedTraceId === session.trace_id
                  const waterfallPct = maxDuration > 0
                    ? (session.total_duration_ns / maxDuration) * 100
                    : 0

                  return (
                    <React.Fragment key={session.trace_id}>
                      <tr
                        onClick={() => handleRowActivate(session)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleRowActivate(session) }
                        }}
                        tabIndex={0}
                        role="button"
                        aria-expanded={isExpanded}
                        style={{ cursor: 'pointer' }}
                        className={isExpanded ? 'selected' : ''}
                      >
                        <td style={{ width: 28, textAlign: 'center', color: 'var(--gray-500)', fontSize: 10 }}>
                          {isExpanded ? '▼' : '▶'}
                        </td>
                        <td className="primary">{session.root_span_name}</td>
                        <td>{session.agent_name || <span className="text-muted">&mdash;</span>}</td>
                        <td className="mono">{session.span_count}</td>
                        <td className="mono">{formatDuration(session.total_duration_ns)}</td>
                        <td>
                          <div className="session-waterfall-track">
                            <div
                              className="session-waterfall-bar"
                              style={{ width: `${Math.max(2, waterfallPct)}%` }}
                            />
                          </div>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                            {session.has_error ? (
                              <span className="badge badge-critical">ERROR</span>
                            ) : (
                              <span className="badge badge-low">OK</span>
                            )}
                            {!session.has_error && session.total_duration_ns >= p95Duration && (
                              <span className="badge badge-medium" title="Duration in top 5% of all sessions">SLOW</span>
                            )}
                          </div>
                        </td>
                        <td className="text-muted">{formatTime(session.start_time)}</td>
                      </tr>

                      {isExpanded && (
                        <tr className="session-expanded-row">
                          <td colSpan={8} style={{ padding: 0 }}>
                            <div className="session-expanded-content">
                              {expandedLoading ? (
                                <div style={{ padding: 'var(--space-4)' }}>
                                  {[...Array(4)].map((_, i) => (
                                    <div key={i} className="loading-skeleton" style={{ height: 32, marginBottom: 2 }} />
                                  ))}
                                </div>
                              ) : expandedError ? (
                                <div style={{ padding: 'var(--space-4)' }}>
                                  <div className="error-banner" role="alert">
                                    <span className="error-banner-text">{expandedError}</span>
                                    <button
                                      className="btn btn-ghost btn-sm error-banner-retry"
                                      onClick={() => handleRowActivate(session)}
                                    >
                                      Retry
                                    </button>
                                  </div>
                                </div>
                              ) : (
                                <>
                                  <div className="trace-inline-header">
                                    <div className="trace-inline-title">Trace Details</div>
                                    <div className="trace-inline-meta">
                                      <span>
                                        <span
                                          style={{
                                            display: 'inline-block',
                                            width: 8,
                                            height: 8,
                                            borderRadius: '50%',
                                            background: session.has_error ? 'var(--risk-critical)' : 'var(--risk-low)',
                                            marginRight: 6,
                                          }}
                                        />
                                        {session.has_error ? 'Error' : 'Healthy'}
                                      </span>
                                      <span>&#9201; {formatDuration(session.total_duration_ns)}</span>
                                      <span>&#9635; {expandedSpans.length} spans</span>
                                    </div>
                                  </div>

                                  <div className="session-trace-layout">
                                    <div className="session-trace-left">
                                      <TraceTreeView
                                        spans={expandedSpans}
                                        selectedSpanId={selectedSpan?.span_id || null}
                                        onSpanSelect={handleSpanSelect}
                                      />
                                    </div>
                                    <div className="session-trace-right">
                                      {selectedSpan ? (
                                        <SpanDetailPanel
                                          span={selectedSpan}
                                          onClose={() => setSelectedSpan(null)}
                                          inline
                                        />
                                      ) : (
                                        <div className="trace-inline-empty">
                                          <p>Select a span from the tree to view details</p>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
