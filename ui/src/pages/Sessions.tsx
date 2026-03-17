import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { fetchSessions, fetchTraceSpans, SessionSummary, SpanDetail, formatDuration } from '../api/sessions'
import TraceTreeView from '../components/TraceTreeView'
import SpanDetailPanel from '../components/SpanDetailPanel'
import { useProject } from '../context/ProjectContext'

type SortKey = 'start_time' | 'total_duration_ns' | 'span_count' | 'root_span_name'

export default function Sessions() {
  const { selectedProject } = useProject()
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('start_time')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  // Inline expansion state
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(null)
  const [expandedSpans, setExpandedSpans] = useState<SpanDetail[]>([])
  const [expandedLoading, setExpandedLoading] = useState(false)
  const [selectedSpan, setSelectedSpan] = useState<SpanDetail | null>(null)

  useEffect(() => {
    setLoading(true)
    fetchSessions(selectedProject)
      .then(setSessions)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedProject])

  const sorted = useMemo(() => {
    const copy = [...sessions]
    copy.sort((a, b) => {
      let cmp = 0
      if (sortKey === 'start_time') cmp = a.start_time.localeCompare(b.start_time)
      else if (sortKey === 'total_duration_ns') cmp = a.total_duration_ns - b.total_duration_ns
      else if (sortKey === 'span_count') cmp = a.span_count - b.span_count
      else if (sortKey === 'root_span_name') cmp = a.root_span_name.localeCompare(b.root_span_name)
      return sortDir === 'asc' ? cmp : -cmp
    })
    return copy
  }, [sessions, sortKey, sortDir])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return ''
    return sortDir === 'asc' ? ' \u2191' : ' \u2193'
  }

  const formatTime = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  }

  const handleRowClick = useCallback((traceId: string) => {
    if (expandedTraceId === traceId) {
      // Collapse
      setExpandedTraceId(null)
      setExpandedSpans([])
      setSelectedSpan(null)
      return
    }
    // Expand
    setExpandedTraceId(traceId)
    setExpandedLoading(true)
    setSelectedSpan(null)
    fetchTraceSpans(traceId)
      .then(setExpandedSpans)
      .catch(() => setExpandedSpans([]))
      .finally(() => setExpandedLoading(false))
  }, [expandedTraceId])

  const handleSpanSelect = useCallback((span: SpanDetail) => {
    setSelectedSpan(span)
  }, [])

  // Compute max duration for waterfall bar sizing
  const maxDuration = useMemo(() => {
    if (sessions.length === 0) return 1
    return Math.max(...sessions.map(s => s.total_duration_ns))
  }, [sessions])

  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Monitor</div>
        <h2>Sessions</h2>
        <p className="page-meta">
          {loading
            ? 'Loading sessions...'
            : `${sessions.length} traces`}
        </p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading ? (
        <div className="table-container">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="loading-skeleton" style={{ height: 44, marginBottom: 2 }} />
          ))}
        </div>
      ) : sessions.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
          </div>
          <h3>No Sessions Yet</h3>
          <p>Sessions will appear here once your instrumented agents start sending traces via OpenTelemetry.</p>
        </div>
      ) : (
        <div className="sessions-list">
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 28 }} />
                  <th onClick={() => toggleSort('root_span_name')} style={{ cursor: 'pointer' }}>
                    Root Span{sortIndicator('root_span_name')}
                  </th>
                  <th>Agent</th>
                  <th onClick={() => toggleSort('span_count')} style={{ cursor: 'pointer' }}>
                    Spans{sortIndicator('span_count')}
                  </th>
                  <th onClick={() => toggleSort('total_duration_ns')} style={{ cursor: 'pointer' }}>
                    Duration{sortIndicator('total_duration_ns')}
                  </th>
                  <th style={{ minWidth: 120 }}>Waterfall</th>
                  <th>Status</th>
                  <th onClick={() => toggleSort('start_time')} style={{ cursor: 'pointer' }}>
                    Time{sortIndicator('start_time')}
                  </th>
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
                        onClick={() => handleRowClick(session.trace_id)}
                        style={{ cursor: 'pointer' }}
                        className={isExpanded ? 'selected' : ''}
                      >
                        <td style={{ width: 28, textAlign: 'center', color: 'var(--gray-500)', fontSize: 10 }}>
                          {isExpanded ? '\u25BC' : '\u25B6'}
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
                          {session.has_error ? (
                            <span className="badge badge-critical">ERROR</span>
                          ) : (
                            <span className="badge badge-low">OK</span>
                          )}
                        </td>
                        <td className="text-muted">{formatTime(session.start_time)}</td>
                      </tr>

                      {/* Inline expansion row — trace tree + detail panel */}
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
                              ) : (
                                <>
                                  {/* Trace header */}
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

                                  {/* Two-column layout: tree + detail */}
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
