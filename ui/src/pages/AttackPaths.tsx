import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { fetchAttackPaths, AttackPath, severityBadgeClass, severityColor } from '../api/risk'
import { useProject } from '../context/ProjectContext'

type SortKey = 'risk_score' | 'owasp_category' | 'rule_name'

export default function AttackPaths() {
  const { selectedProject } = useProject()
  const [paths, setPaths] = useState<AttackPath[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('risk_score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [expandedPathId, setExpandedPathId] = useState<string | null>(null)

  useEffect(() => { document.title = 'Attack Paths — TraceCtrl' }, [])

  useEffect(() => {
    setLoading(true)
    fetchAttackPaths(selectedProject)
      .then(setPaths)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedProject])

  const sorted = useMemo(() => {
    const copy = [...paths]
    copy.sort((a, b) => {
      let cmp = 0
      if (sortKey === 'risk_score') cmp = a.risk_score - b.risk_score
      else if (sortKey === 'owasp_category') cmp = a.owasp_category.localeCompare(b.owasp_category)
      else if (sortKey === 'rule_name') cmp = a.rule_name.localeCompare(b.rule_name)
      return sortDir === 'asc' ? cmp : -cmp
    })
    return copy
  }, [paths, sortKey, sortDir])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return ''
    return sortDir === 'asc' ? ' \u2191' : ' \u2193'
  }

  const handleRowClick = useCallback((pathId: string) => {
    setExpandedPathId(expandedPathId === pathId ? null : pathId)
  }, [expandedPathId])

  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Security</div>
        <h2>Attack Paths</h2>
        <p className="page-meta" aria-live="polite">
          {loading
            ? 'Loading attack paths...'
            : `${paths.length} paths`}
        </p>
      </div>

      {error && (
        <div className="error-banner">
          {error}
          <button className="btn btn-ghost btn-sm" style={{ marginLeft: 'auto' }} onClick={() => { setError(null); setLoading(true); fetchAttackPaths(selectedProject).then(setPaths).catch(err => setError(err.message)).finally(() => setLoading(false)); }}>
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <div className="table-container">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="loading-skeleton" style={{ height: 44, marginBottom: 2 }} />
          ))}
        </div>
      ) : paths.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
            </svg>
          </div>
          <h3>No Attack Paths Detected</h3>
          <p>No attack paths detected — your agents look secure!</p>
        </div>
      ) : (
        <div className="sessions-list">
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 28 }} />
                  <th onClick={() => toggleSort('risk_score')} style={{ cursor: 'pointer' }} aria-sort={sortKey === 'risk_score' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    Risk Score{sortIndicator('risk_score')}
                  </th>
                  <th>Severity</th>
                  <th onClick={() => toggleSort('owasp_category')} style={{ cursor: 'pointer' }} aria-sort={sortKey === 'owasp_category' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    OWASP Category{sortIndicator('owasp_category')}
                  </th>
                  <th onClick={() => toggleSort('rule_name')} style={{ cursor: 'pointer' }} aria-sort={sortKey === 'rule_name' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    Rule Name{sortIndicator('rule_name')}
                  </th>
                  <th>Agents Involved</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map(path => {
                  const isExpanded = expandedPathId === path.path_id

                  return (
                    <React.Fragment key={path.path_id}>
                      <tr
                        onClick={() => handleRowClick(path.path_id)}
                        style={{ cursor: 'pointer' }}
                        className={isExpanded ? 'selected' : ''}
                        aria-expanded={isExpanded}
                      >
                        <td style={{ width: 28, textAlign: 'center', color: 'var(--gray-500)', fontSize: 10 }}>
                          {isExpanded ? '\u25BC' : '\u25B6'}
                        </td>
                        <td className="mono" style={{ color: severityColor(path.severity) }}>
                          {path.risk_score}
                        </td>
                        <td>
                          <span className={`badge ${severityBadgeClass(path.severity)}`}>
                            {path.severity.toUpperCase()}
                          </span>
                        </td>
                        <td className="mono">{path.owasp_category}</td>
                        <td className="primary">{path.rule_name}</td>
                        <td>{path.agents_involved.join(', ')}</td>
                      </tr>

                      {isExpanded && (
                        <tr className="session-expanded-row">
                          <td colSpan={6} style={{ padding: 0 }}>
                            <div className="session-expanded-content">
                              <div style={{ padding: 'var(--space-4)' }}>
                                <div className="trace-inline-header">
                                  <div className="trace-inline-title">Attack Chain</div>
                                  <div className="trace-inline-meta">
                                    <span>{path.path_steps.length} steps</span>
                                  </div>
                                </div>
                                {path.path_steps.length === 0 ? (
                                  <div style={{ color: 'var(--gray-500)', padding: 'var(--space-2) 0' }}>
                                    No steps recorded for this path.
                                  </div>
                                ) : (
                                  <table className="table" style={{ marginTop: 'var(--space-2)' }}>
                                    <thead>
                                      <tr>
                                        <th style={{ width: 40 }}>#</th>
                                        <th>Node ID</th>
                                        <th>Type</th>
                                        <th>Vulnerability</th>
                                        <th>Description</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {path.path_steps.map((step, idx) => (
                                        <tr key={step.node_id}>
                                          <td className="mono">{idx + 1}</td>
                                          <td className="mono">{step.node_id}</td>
                                          <td><span className="badge">{step.node_type}</span></td>
                                          <td className="primary">{step.vulnerability}</td>
                                          <td>{step.description}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                )}
                              </div>
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
