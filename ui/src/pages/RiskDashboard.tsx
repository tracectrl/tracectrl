import { useEffect, useState, useMemo } from 'react'
import { useProject } from '../context/ProjectContext'
import { fetchRiskSummary, fetchAgentRisks, RiskSummary, AgentRisk, severityBadgeClass, severityColor } from '../api/risk'

type SortKey = 'agent_id' | 'risk_score' | 'severity' | 'path_count'

const SEVERITY_ORDER: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 }

export default function RiskDashboard() {
  const { selectedProject } = useProject()
  const [summary, setSummary] = useState<RiskSummary | null>(null)
  const [agentRisks, setAgentRisks] = useState<AgentRisk[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('risk_score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  useEffect(() => {
    setLoading(true)
    Promise.all([fetchRiskSummary(), fetchAgentRisks(selectedProject)])
      .then(([s, a]) => { setSummary(s); setAgentRisks(a) })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedProject])

  const sorted = useMemo(() => {
    const copy = [...agentRisks]
    copy.sort((a, b) => {
      let cmp = 0
      if (sortKey === 'agent_id') cmp = a.agent_id.localeCompare(b.agent_id)
      else if (sortKey === 'risk_score') cmp = a.risk_score - b.risk_score
      else if (sortKey === 'severity') cmp = (SEVERITY_ORDER[a.severity.toLowerCase()] || 0) - (SEVERITY_ORDER[b.severity.toLowerCase()] || 0)
      else if (sortKey === 'path_count') cmp = a.path_count - b.path_count
      return sortDir === 'asc' ? cmp : -cmp
    })
    return copy
  }, [agentRisks, sortKey, sortDir])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return ''
    return sortDir === 'asc' ? ' \u2191' : ' \u2193'
  }

  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Security</div>
        <h2>Risk Dashboard</h2>
        <p className="page-meta">
          {loading
            ? 'Calculating risk...'
            : summary
              ? `System score ${summary.risk_score} \u2014 ${summary.severity}`
              : 'No risk data available'}
        </p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading ? (
        <>
          {/* Skeleton for hero + cards */}
          <div className="loading-skeleton" style={{ height: 80, marginBottom: 16 }} />
          <div className="card-grid cols-4" style={{ marginBottom: 24 }}>
            {[...Array(4)].map((_, i) => (
              <div key={i} className="loading-skeleton" style={{ height: 80 }} />
            ))}
          </div>
          <div className="table-container">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="loading-skeleton" style={{ height: 44, marginBottom: 2 }} />
            ))}
          </div>
        </>
      ) : !summary && agentRisks.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <h3>No Risk Data Yet</h3>
          <p>Risk scores will appear once attack path analysis has been run against your agent topology.</p>
        </div>
      ) : (
        <>
          {/* System risk hero */}
          {summary && (
            <div className="stat-card" style={{ textAlign: 'center', marginBottom: 'var(--space-4)', padding: 'var(--space-4)' }}>
              <div className="stat-value" style={{ fontSize: 48, color: severityColor(summary.severity) }}>
                {summary.risk_score}
              </div>
              <div className="stat-label" style={{ color: severityColor(summary.severity) }}>
                {summary.severity.toUpperCase()} RISK
              </div>
            </div>
          )}

          {/* 4-stat card grid */}
          {summary && (
            <div className="card-grid cols-4" style={{ marginBottom: 'var(--space-6)' }}>
              <div className="stat-card">
                <div className="stat-value">{summary.critical_paths}</div>
                <div className="stat-label">Critical Paths</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{summary.agents_at_risk}</div>
                <div className="stat-label">Agents at Risk</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{summary.learning_agents}</div>
                <div className="stat-label">Learning Agents</div>
              </div>
              <div className="stat-card">
                <div className="stat-value" style={{ color: severityColor(summary.severity) }}>
                  {summary.severity.toUpperCase()}
                </div>
                <div className="stat-label">Overall Severity</div>
              </div>
            </div>
          )}

          {/* Per-agent risk table */}
          {agentRisks.length > 0 && (
            <div className="sessions-list">
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      <th onClick={() => toggleSort('agent_id')} style={{ cursor: 'pointer' }}>
                        Agent ID{sortIndicator('agent_id')}
                      </th>
                      <th onClick={() => toggleSort('risk_score')} style={{ cursor: 'pointer' }}>
                        Risk Score{sortIndicator('risk_score')}
                      </th>
                      <th onClick={() => toggleSort('severity')} style={{ cursor: 'pointer' }}>
                        Severity{sortIndicator('severity')}
                      </th>
                      <th onClick={() => toggleSort('path_count')} style={{ cursor: 'pointer' }}>
                        Paths{sortIndicator('path_count')}
                      </th>
                      <th>Top Rule</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map(agent => (
                      <tr key={agent.agent_id}>
                        <td className="primary">{agent.agent_id}</td>
                        <td className="mono" style={{ color: severityColor(agent.severity) }}>
                          {agent.risk_score}
                        </td>
                        <td>
                          <span className={`badge ${severityBadgeClass(agent.severity)}`}>
                            {agent.severity.toUpperCase()}
                          </span>
                        </td>
                        <td className="mono">{agent.path_count}</td>
                        <td>{agent.top_rule || <span className="text-muted">&mdash;</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
