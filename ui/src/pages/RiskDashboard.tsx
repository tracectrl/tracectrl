import { useEffect, useState, useMemo, useCallback } from 'react'
import { useProject } from '../context/ProjectContext'
import { fetchRiskSummary, fetchAgentRisks, RiskSummary, AgentRisk, severityBadgeClass, severityColor } from '../api/risk'
import SortableTh from '../components/shared/SortableTh'
import EmptyState from '../components/shared/EmptyState'
import ErrorBanner from '../components/shared/ErrorBanner'

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

  useEffect(() => { document.title = 'Risk Dashboard — TraceCtrl' }, [])

  const load = useCallback(() => {
    setError(null)
    setLoading(true)
    Promise.all([fetchRiskSummary(), fetchAgentRisks(selectedProject)])
      .then(([s, a]) => { setSummary(s); setAgentRisks(a) })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedProject])

  useEffect(() => { load() }, [load])

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

  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Security</div>
        <h2>Risk Dashboard</h2>
        <p className="page-meta" aria-live="polite">
          {loading
            ? 'Calculating risk...'
            : summary
              ? `System score ${summary.risk_score} — ${summary.severity}`
              : 'No risk data available'}
        </p>
      </div>

      {error && <ErrorBanner error={error} onRetry={load} />}

      {loading ? (
        <>
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
        <EmptyState
          title="No Risk Data Yet"
          hint="Risk scores will appear once attack path analysis has been run against your agent topology."
          icon={
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          }
        />
      ) : (
        <>
          {summary && (
            <div className="card-grid cols-4" style={{ marginBottom: 'var(--space-6)' }}>
              <div className="stat-card">
                <div className="stat-label">Risk Score</div>
                <div className="stat-value mono">{summary.risk_score}</div>
                <span className={`badge ${severityBadgeClass(summary.severity)}`}>{summary.severity.toUpperCase()}</span>
              </div>
              <div className="stat-card">
                <div className="stat-label">Critical Paths</div>
                <div className="stat-value">{summary.critical_paths}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Agents at Risk</div>
                <div className="stat-value">{summary.agents_at_risk}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Learning Agents</div>
                <div className="stat-value">{summary.learning_agents}</div>
              </div>
            </div>
          )}

          {agentRisks.length > 0 && (
            <div className="sessions-list">
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      <SortableTh active={sortKey === 'agent_id'} direction={sortDir} onToggle={() => toggleSort('agent_id')}>Agent ID</SortableTh>
                      <SortableTh active={sortKey === 'risk_score'} direction={sortDir} onToggle={() => toggleSort('risk_score')}>Risk Score</SortableTh>
                      <SortableTh active={sortKey === 'severity'} direction={sortDir} onToggle={() => toggleSort('severity')}>Severity</SortableTh>
                      <SortableTh active={sortKey === 'path_count'} direction={sortDir} onToggle={() => toggleSort('path_count')}>Paths</SortableTh>
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
