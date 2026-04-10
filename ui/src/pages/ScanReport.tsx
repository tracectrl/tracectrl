import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { fetchLatestScan, ScanResult } from '../api/scan'

type SortKey = 'check_id' | 'section' | 'severity' | 'title'

const SEVERITY_ORDER: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1, pass: 0 }

function severityBadgeClass(severity: string): string {
  const s = severity.toLowerCase()
  if (s === 'critical') return 'badge-critical'
  if (s === 'high') return 'badge-high'
  if (s === 'medium') return 'badge-medium'
  return 'badge-low'
}

export default function ScanReport() {
  const [results, setResults] = useState<ScanResult[]>([])
  const [scanId, setScanId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('severity')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [expandedRow, setExpandedRow] = useState<string | null>(null)

  useEffect(() => { document.title = 'Scan Report \u2014 TraceCtrl' }, [])

  const loadData = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchLatestScan()
      .then(data => {
        setScanId(data.scan_id)
        setResults(data.results)
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const sorted = useMemo(() => {
    const copy = [...results]
    copy.sort((a, b) => {
      let cmp = 0
      if (sortKey === 'check_id') cmp = a.check_id.localeCompare(b.check_id)
      else if (sortKey === 'section') cmp = a.section.localeCompare(b.section)
      else if (sortKey === 'severity') {
        const aOrd = a.passed === 1 ? 0 : (SEVERITY_ORDER[a.severity.toLowerCase()] || 0)
        const bOrd = b.passed === 1 ? 0 : (SEVERITY_ORDER[b.severity.toLowerCase()] || 0)
        cmp = aOrd - bOrd
      }
      else if (sortKey === 'title') cmp = a.title.localeCompare(b.title)
      return sortDir === 'asc' ? cmp : -cmp
    })
    return copy
  }, [results, sortKey, sortDir])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return ''
    return sortDir === 'asc' ? ' \u2191' : ' \u2193'
  }

  const counts = useMemo(() => {
    let critical = 0, high = 0, medium = 0, passed = 0
    for (const r of results) {
      if (r.passed === 1) { passed++; continue }
      const s = r.severity.toLowerCase()
      if (s === 'critical') critical++
      else if (s === 'high') high++
      else if (s === 'medium') medium++
      else passed++
    }
    return { critical, high, medium, pass: passed }
  }, [results])

  const meta = results.length > 0 ? results[0] : null

  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Security</div>
        <h2>OpenClaw Security Scan</h2>
        <p className="page-meta" aria-live="polite">
          {loading
            ? 'Loading scan results...'
            : scanId
              ? `Scan ${scanId} \u2014 ${meta?.scanned_at ?? ''} \u2014 ${meta?.openclaw_path ?? ''}`
              : 'No scans available'}
        </p>
      </div>

      {error && (
        <div className="error-banner">
          {error}
          <button
            className="btn btn-ghost btn-sm"
            style={{ marginLeft: 'auto' }}
            onClick={loadData}
          >
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <>
          <div className="scan-severity-grid">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="loading-skeleton" style={{ height: 90 }} />
            ))}
          </div>
          <div className="table-container">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="loading-skeleton" style={{ height: 44, marginBottom: 2 }} />
            ))}
          </div>
        </>
      ) : results.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <h3>No Scan Results Yet</h3>
          <p>Run an OpenClaw security scan to see compliance findings here.</p>
        </div>
      ) : (
        <>
          {/* Severity summary cards */}
          <div className="scan-severity-grid">
            <div className="scan-severity-card">
              <div className="scan-severity-count" style={{ color: 'var(--risk-critical)' }}>
                {counts.critical}
              </div>
              <div className="scan-severity-label">Critical</div>
            </div>
            <div className="scan-severity-card">
              <div className="scan-severity-count" style={{ color: 'var(--risk-high)' }}>
                {counts.high}
              </div>
              <div className="scan-severity-label">High</div>
            </div>
            <div className="scan-severity-card">
              <div className="scan-severity-count" style={{ color: 'var(--risk-medium)' }}>
                {counts.medium}
              </div>
              <div className="scan-severity-label">Medium</div>
            </div>
            <div className="scan-severity-card">
              <div className="scan-severity-count" style={{ color: 'var(--risk-low)' }}>
                {counts.pass}
              </div>
              <div className="scan-severity-label">Pass</div>
            </div>
          </div>

          {/* Findings table */}
          <div className="sessions-list">
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th
                      onClick={() => toggleSort('check_id')}
                      style={{ cursor: 'pointer' }}
                      aria-sort={sortKey === 'check_id' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    >
                      Check{sortIndicator('check_id')}
                    </th>
                    <th
                      onClick={() => toggleSort('section')}
                      style={{ cursor: 'pointer' }}
                      aria-sort={sortKey === 'section' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    >
                      Section{sortIndicator('section')}
                    </th>
                    <th
                      onClick={() => toggleSort('severity')}
                      style={{ cursor: 'pointer' }}
                      aria-sort={sortKey === 'severity' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    >
                      Severity{sortIndicator('severity')}
                    </th>
                    <th
                      onClick={() => toggleSort('title')}
                      style={{ cursor: 'pointer' }}
                      aria-sort={sortKey === 'title' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    >
                      Title{sortIndicator('title')}
                    </th>
                    <th>Finding</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map(r => {
                    const rowKey = `${r.scan_id}-${r.check_id}`
                    const isExpanded = expandedRow === rowKey
                    return (
                      <React.Fragment key={rowKey}>
                        <tr
                          onClick={() => setExpandedRow(isExpanded ? null : rowKey)}
                          style={{ cursor: 'pointer' }}
                          aria-expanded={isExpanded}
                        >
                          <td className="mono">{r.check_id}</td>
                          <td>{r.section}</td>
                          <td>
                            {r.passed === 1 ? (
                              <span className="badge badge-low">PASS</span>
                            ) : (
                              <span className={`badge ${severityBadgeClass(r.severity)}`}>
                                {r.severity.toUpperCase()}
                              </span>
                            )}
                          </td>
                          <td className="primary">{r.title}</td>
                          <td>{r.finding}</td>
                        </tr>
                        {isExpanded && (
                          <tr>
                            <td colSpan={5} style={{ padding: 0 }}>
                              <div className="scan-remediation">
                                <strong>Remediation:</strong> {r.remediation || 'No remediation guidance available.'}
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
        </>
      )}
    </div>
  )
}
