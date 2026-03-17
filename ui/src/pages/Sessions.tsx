import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchSessions, SessionSummary, formatDuration } from '../api/sessions'

type SortKey = 'start_time' | 'total_duration_ns' | 'span_count' | 'root_span_name'

export default function Sessions() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('start_time')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  useEffect(() => {
    fetchSessions()
      .then(setSessions)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

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
    return sortDir === 'asc' ? ' ↑' : ' ↓'
  }

  const formatTime = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  }

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
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
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
                <th>Status</th>
                <th onClick={() => toggleSort('start_time')} style={{ cursor: 'pointer' }}>
                  Time{sortIndicator('start_time')}
                </th>
                <th>Trace ID</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(session => (
                <tr
                  key={session.trace_id}
                  onClick={() => navigate(`/sessions/${session.trace_id}`)}
                  style={{ cursor: 'pointer' }}
                >
                  <td className="primary">{session.root_span_name}</td>
                  <td>{session.agent_name || <span className="text-muted">—</span>}</td>
                  <td className="mono">{session.span_count}</td>
                  <td className="mono">{formatDuration(session.total_duration_ns)}</td>
                  <td>
                    {session.has_error ? (
                      <span className="badge badge-critical">ERROR</span>
                    ) : (
                      <span className="badge badge-low">OK</span>
                    )}
                  </td>
                  <td className="text-muted">{formatTime(session.start_time)}</td>
                  <td className="mono text-muted" title={session.trace_id}>
                    {session.trace_id.slice(-8)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
