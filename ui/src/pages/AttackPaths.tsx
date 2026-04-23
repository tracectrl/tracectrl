import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { fetchAttackPaths, AttackPath, severityBadgeClass, severityColor } from '../api/risk'
import SortableTh from '../components/shared/SortableTh'
import EmptyState from '../components/shared/EmptyState'
import ErrorBanner from '../components/shared/ErrorBanner'
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

  const load = useCallback(() => {
    setError(null)
    setLoading(true)
    fetchAttackPaths(selectedProject)
      .then(setPaths)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedProject])

  useEffect(() => { load() }, [load])

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

  const handleRowActivate = useCallback((pathId: string) => {
    setExpandedPathId(prev => prev === pathId ? null : pathId)
  }, [])

  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Security</div>
        <h2>Attack Paths</h2>
        <p className="page-meta" aria-live="polite">
          {loading ? 'Loading attack paths...' : `${paths.length} paths`}
        </p>
      </div>

      {error && <ErrorBanner error={error} onRetry={load} />}

      {loading ? (
        <div className="table-container">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="loading-skeleton" style={{ height: 44, marginBottom: 2 }} />
          ))}
        </div>
      ) : paths.length === 0 ? (
        <EmptyState
          title="No Attack Paths Detected"
          hint="No attack paths detected — your agents look secure."
          icon={
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
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
                  <SortableTh active={sortKey === 'risk_score'} direction={sortDir} onToggle={() => toggleSort('risk_score')}>Risk Score</SortableTh>
                  <th>Severity</th>
                  <SortableTh active={sortKey === 'owasp_category'} direction={sortDir} onToggle={() => toggleSort('owasp_category')}>OWASP Category</SortableTh>
                  <SortableTh active={sortKey === 'rule_name'} direction={sortDir} onToggle={() => toggleSort('rule_name')}>Rule Name</SortableTh>
                  <th>Agents Involved</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map(path => {
                  const isExpanded = expandedPathId === path.path_id
                  return (
                    <React.Fragment key={path.path_id}>
                      <tr
                        onClick={() => handleRowActivate(path.path_id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleRowActivate(path.path_id) }
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
