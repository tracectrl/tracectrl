import { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import SpanTree from '../components/SpanTree'
import SpanDetailPanel from '../components/SpanDetailPanel'
import { fetchTraceSpans, SpanDetail, formatDuration } from '../api/sessions'

export default function TraceDetail() {
  const { traceId } = useParams<{ traceId: string }>()
  const navigate = useNavigate()
  const [spans, setSpans] = useState<SpanDetail[]>([])
  const [selectedSpan, setSelectedSpan] = useState<SpanDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!traceId) return
    fetchTraceSpans(traceId)
      .then(setSpans)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [traceId])

  const handleSpanSelect = useCallback((span: SpanDetail) => {
    setSelectedSpan(span)
  }, [])

  const traceStartNs = useMemo(() => {
    if (spans.length === 0) return 0
    return Math.min(...spans.map(s => s.start_ns))
  }, [spans])

  const traceDurationNs = useMemo(() => {
    if (spans.length === 0) return 0
    const maxEnd = Math.max(...spans.map(s => s.start_ns + s.duration_ns))
    return maxEnd - traceStartNs
  }, [spans, traceStartNs])

  const rootSpan = useMemo(() => {
    return spans.find(s => !s.parent_span_id) || spans[0]
  }, [spans])

  return (
    <div>
      <div className="page-header">
        <button className="btn btn-ghost btn-sm mb-2" onClick={() => navigate('/sessions')}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 1L3 7l6 6" />
          </svg>
          Back to Sessions
        </button>
        <div className="section-tag">Trace</div>
        <h2>{rootSpan?.span_name || 'Loading...'}</h2>
        <p className="page-meta">
          {loading
            ? 'Loading spans...'
            : `${spans.length} spans · ${formatDuration(traceDurationNs)} · ${traceId?.slice(-8)}`}
        </p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading ? (
        <div className="table-container">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="loading-skeleton" style={{ height: 36, marginBottom: 2 }} />
          ))}
        </div>
      ) : (
        <div className="trace-detail-layout">
          <div className="trace-tree-area">
            <div className="table-container">
              <SpanTree
                spans={spans}
                traceDurationNs={traceDurationNs}
                traceStartNs={traceStartNs}
                selectedSpanId={selectedSpan?.span_id || null}
                onSpanSelect={handleSpanSelect}
              />
            </div>
          </div>
          <SpanDetailPanel span={selectedSpan} onClose={() => setSelectedSpan(null)} />
        </div>
      )}
    </div>
  )
}
