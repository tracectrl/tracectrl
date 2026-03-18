import React, { useEffect, useState, useMemo, useCallback } from 'react'
import { fetchAgentList, fetchAgentTools, AgentSummary, AgentTool } from '../api/agents'
import { useProject } from '../context/ProjectContext'

type SortKey = 'name' | 'observation_count' | 'last_seen' | 'tools_count'

export default function Agents() {
  const { selectedProject } = useProject()
  const [agents, setAgents] = useState<AgentSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('last_seen')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [expandedAgentId, setExpandedAgentId] = useState<string | null>(null)
  const [expandedTools, setExpandedTools] = useState<AgentTool[]>([])
  const [expandedLoading, setExpandedLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    fetchAgentList(selectedProject)
      .then(setAgents)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [selectedProject])

  const sorted = useMemo(() => {
    const copy = [...agents]
    copy.sort((a, b) => {
      let cmp = 0
      if (sortKey === 'name') cmp = (a.name || a.agent_id).localeCompare(b.name || b.agent_id)
      else if (sortKey === 'observation_count') cmp = a.observation_count - b.observation_count
      else if (sortKey === 'last_seen') cmp = a.last_seen.localeCompare(b.last_seen)
      else if (sortKey === 'tools_count') cmp = a.tools_observed.length - b.tools_observed.length
      return sortDir === 'asc' ? cmp : -cmp
    })
    return copy
  }, [agents, sortKey, sortDir])

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

  const handleRowClick = useCallback((agentId: string) => {
    if (expandedAgentId === agentId) {
      setExpandedAgentId(null)
      setExpandedTools([])
      return
    }
    setExpandedAgentId(agentId)
    setExpandedLoading(true)
    fetchAgentTools(agentId)
      .then(setExpandedTools)
      .catch(() => setExpandedTools([]))
      .finally(() => setExpandedLoading(false))
  }, [expandedAgentId])

  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Monitor</div>
        <h2>Agents</h2>
        <p className="page-meta">
          {loading
            ? 'Loading agents...'
            : `${agents.length} agents`}
        </p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading ? (
        <div className="table-container">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="loading-skeleton" style={{ height: 44, marginBottom: 2 }} />
          ))}
        </div>
      ) : agents.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
              <path d="M16 3.13a4 4 0 0 1 0 7.75" />
            </svg>
          </div>
          <h3>No Agents Discovered</h3>
          <p>Agents will appear here once your instrumented applications start sending traces via OpenTelemetry.</p>
        </div>
      ) : (
        <div className="sessions-list">
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: 28 }} />
                  <th onClick={() => toggleSort('name')} style={{ cursor: 'pointer' }}>
                    Name{sortIndicator('name')}
                  </th>
                  <th>Framework</th>
                  <th>Model</th>
                  <th onClick={() => toggleSort('tools_count')} style={{ cursor: 'pointer' }}>
                    Tools{sortIndicator('tools_count')}
                  </th>
                  <th onClick={() => toggleSort('observation_count')} style={{ cursor: 'pointer' }}>
                    Observations{sortIndicator('observation_count')}
                  </th>
                  <th>Maturity</th>
                  <th onClick={() => toggleSort('last_seen')} style={{ cursor: 'pointer' }}>
                    Last Seen{sortIndicator('last_seen')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sorted.map(agent => {
                  const isExpanded = expandedAgentId === agent.agent_id

                  return (
                    <React.Fragment key={agent.agent_id}>
                      <tr
                        onClick={() => handleRowClick(agent.agent_id)}
                        style={{ cursor: 'pointer' }}
                        className={isExpanded ? 'selected' : ''}
                      >
                        <td style={{ width: 28, textAlign: 'center', color: 'var(--gray-500)', fontSize: 10 }}>
                          {isExpanded ? '\u25BC' : '\u25B6'}
                        </td>
                        <td className="primary">{agent.name || agent.agent_id}</td>
                        <td><span className="badge">{agent.framework}</span></td>
                        <td className="mono">{agent.model}</td>
                        <td className="mono">{agent.tools_observed.length}</td>
                        <td className="mono">{agent.observation_count}</td>
                        <td>
                          {agent.maturity === 'MATURE' ? (
                            <span className="badge badge-low">MATURE</span>
                          ) : (
                            <span className="badge badge-medium">LEARNING</span>
                          )}
                        </td>
                        <td className="text-muted">{formatTime(agent.last_seen)}</td>
                      </tr>

                      {isExpanded && (
                        <tr className="session-expanded-row">
                          <td colSpan={8} style={{ padding: 0 }}>
                            <div className="session-expanded-content">
                              {expandedLoading ? (
                                <div style={{ padding: 'var(--space-4)' }}>
                                  {[...Array(3)].map((_, i) => (
                                    <div key={i} className="loading-skeleton" style={{ height: 32, marginBottom: 2 }} />
                                  ))}
                                </div>
                              ) : expandedTools.length === 0 ? (
                                <div style={{ padding: 'var(--space-4)', color: 'var(--gray-500)' }}>
                                  No tool usage recorded for this agent.
                                </div>
                              ) : (
                                <div style={{ padding: 'var(--space-4)' }}>
                                  <div className="trace-inline-header">
                                    <div className="trace-inline-title">Tools</div>
                                    <div className="trace-inline-meta">
                                      <span>{expandedTools.length} tools observed</span>
                                    </div>
                                  </div>
                                  <table className="table" style={{ marginTop: 'var(--space-2)' }}>
                                    <thead>
                                      <tr>
                                        <th>Tool Name</th>
                                        <th>Category</th>
                                        <th>Calls</th>
                                        <th>Errors</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {expandedTools.map(tool => (
                                        <tr key={tool.tool_name}>
                                          <td className="primary">{tool.tool_name}</td>
                                          <td><span className="badge">{tool.tool_category}</span></td>
                                          <td className="mono">{tool.call_count}</td>
                                          <td className="mono">{tool.error_count > 0 ? (
                                            <span style={{ color: 'var(--risk-critical)' }}>{tool.error_count}</span>
                                          ) : '0'}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
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
