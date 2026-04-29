import { useEffect, useState, useMemo, useCallback } from 'react'
import { fetchAgentList, AgentSummary } from '../api/agents'
import EmptyState from '../components/shared/EmptyState'
import ErrorBanner from '../components/shared/ErrorBanner'
import AgentDetailPanel from '../components/AgentDetailPanel'
import { useProject } from '../context/ProjectContext'

export default function Agents() {
  const { selectedProject } = useProject()
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<AgentSummary | null>(null)

  useEffect(() => { document.title = 'Agents — TraceCtrl' }, [])

  const load = useCallback(() => {
    setError(null)
    setLoading(true)
    fetchAgentList(selectedProject)
      .then(setAgents)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedProject])

  useEffect(() => { load() }, [load])

  const grouped = useMemo(() => {
    // Bucket by framework so related agents stay together. Unknown frameworks
    // fall under "Other" so the page never has rogue ungrouped rows.
    const buckets: Record<string, AgentSummary[]> = {}
    for (const a of agents) {
      const key = (a.framework || 'other').toLowerCase()
      if (!buckets[key]) buckets[key] = []
      buckets[key].push(a)
    }
    const order = ['strands', 'agno', 'openclaw', 'langchain', 'openai', 'other']
    const sorted: { framework: string; agents: AgentSummary[] }[] = []
    for (const k of order) {
      if (buckets[k]) {
        sorted.push({
          framework: k,
          agents: [...buckets[k]].sort((a, b) => b.last_seen.localeCompare(a.last_seen)),
        })
        delete buckets[k]
      }
    }
    for (const k of Object.keys(buckets)) {
      sorted.push({
        framework: k,
        agents: [...buckets[k]].sort((a, b) => b.last_seen.localeCompare(a.last_seen)),
      })
    }
    return sorted
  }, [agents])

  const formatRelative = (iso: string) => {
    const ms = Date.now() - new Date(iso).getTime()
    if (ms < 60_000) return 'just now'
    if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`
    if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`
    return `${Math.floor(ms / 86_400_000)}d ago`
  }

  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Monitor</div>
        <h2>Agents</h2>
        <p className="page-meta" aria-live="polite">
          {loading ? 'Loading agents...' : `${agents.length} agents`}
        </p>
      </div>

      {error && <ErrorBanner error={error} onRetry={load} />}

      {loading ? (
        <div className="agent-grid">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="loading-skeleton" style={{ height: 110 }} />
          ))}
        </div>
      ) : agents.length === 0 ? (
        <EmptyState
          title="No Agents Discovered"
          hint="Agents will appear here once your instrumented applications start sending traces via OpenTelemetry."
          icon={
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          }
        />
      ) : (
        <div className="agent-groups">
          {grouped.map(group => (
            <section key={group.framework} className="agent-group">
              <header className="agent-group-head">
                <h3 className="agent-group-title">{group.framework}</h3>
                <span className="agent-group-count">{group.agents.length}</span>
              </header>
              <div className="agent-grid">
                {group.agents.map(agent => (
                  <button
                    key={agent.agent_id}
                    className="agent-card"
                    onClick={() => setSelected(agent)}
                    aria-label={`Open ${agent.name || agent.agent_id} details`}
                  >
                    <div className="agent-card-head">
                      <div className="agent-card-name" title={agent.name || agent.agent_id}>
                        {agent.name || agent.agent_id}
                      </div>
                      <span className={`badge ${agent.maturity === 'MATURE' ? 'badge-low' : 'badge-medium'}`}>
                        {agent.maturity}
                      </span>
                    </div>
                    <div className="agent-card-meta">
                      <span className="agent-card-meta-item mono" title={agent.model || 'no model recorded'}>
                        {agent.model || '—'}
                      </span>
                    </div>
                    <div className="agent-card-stats">
                      <div className="agent-stat">
                        <span className="agent-stat-value mono">{agent.tools_observed.length}</span>
                        <span className="agent-stat-label">tools</span>
                      </div>
                      <div className="agent-stat">
                        <span className="agent-stat-value mono">{agent.total_tool_calls}</span>
                        <span className="agent-stat-label">tool calls</span>
                      </div>
                      <div className="agent-stat">
                        <span className="agent-stat-value mono">{agent.run_count}</span>
                        <span className="agent-stat-label">runs</span>
                      </div>
                    </div>
                    <div className="agent-card-foot text-muted">
                      Last seen {formatRelative(agent.last_seen)}
                    </div>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      <AgentDetailPanel agent={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
