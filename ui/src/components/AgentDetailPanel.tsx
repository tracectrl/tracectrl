import { useEffect, useState } from 'react'
import Drawer, { DrawerClose } from './shared/Drawer'
import { AgentSummary, AgentTool, fetchAgentTools } from '../api/agents'
import { fetchAgentGuardrails, GuardrailRegistration } from '../api/guardrails'
import GuardrailCard from './GuardrailCard'

interface Props {
  agent: AgentSummary | null
  onClose: () => void
  placement?: 'right' | 'bottom'
}

type Tab = 'overview' | 'prompt' | 'tools' | 'guardrails'

export default function AgentDetailPanel({ agent, onClose, placement = 'right' }: Props) {
  const [tab, setTab] = useState<Tab>('overview')
  const [tools, setTools] = useState<AgentTool[]>([])
  const [toolsLoading, setToolsLoading] = useState(false)
  const [copied, setCopied] = useState(false)
  const [guardrails, setGuardrails] = useState<GuardrailRegistration[]>([])
  const [guardrailsLoading, setGuardrailsLoading] = useState(false)

  useEffect(() => {
    if (!agent) return
    setTab('overview')
    setToolsLoading(true)
    fetchAgentTools(agent.agent_id)
      .then(setTools)
      .catch(() => setTools([]))
      .finally(() => setToolsLoading(false))

    setGuardrailsLoading(true)
    fetchAgentGuardrails(agent.agent_id)
      .then(setGuardrails)
      .catch(() => setGuardrails([]))
      .finally(() => setGuardrailsLoading(false))
  }, [agent])

  const handleCopyPrompt = () => {
    if (!agent?.system_prompt) return
    navigator.clipboard.writeText(agent.system_prompt).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    })
  }

  const formatTime = (iso: string) => {
    if (!iso) return '—'
    const d = new Date(iso)
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    })
  }

  return (
    <Drawer
      open={!!agent}
      onClose={onClose}
      ariaLabel="Agent details"
      widthPx={520}
      heightPx={520}
      placement={placement}
    >
      {agent && (
        <>
          <header className="drawer-head">
            <div className="drawer-title-row">
              <div>
                <div className="drawer-eyebrow">{agent.framework || 'agent'}</div>
                <h3 className="drawer-title">{agent.name || agent.agent_id}</h3>
              </div>
              <DrawerClose onClose={onClose} />
            </div>
            <div className="drawer-meta-row">
              <span className="meta-chip">
                <span className="meta-chip-label">Model</span>
                <span className="meta-chip-value mono">{agent.model || '—'}</span>
              </span>
              <span className="meta-chip">
                <span className="meta-chip-label">Tools</span>
                <span className="meta-chip-value mono">{agent.total_tool_calls}</span>
              </span>
              <span className="meta-chip">
                <span className="meta-chip-label">Runs</span>
                <span className="meta-chip-value mono">{agent.run_count}</span>
              </span>
              <span className={`badge ${agent.maturity === 'MATURE' ? 'badge-low' : 'badge-medium'}`}>
                {agent.maturity}
              </span>
            </div>
          </header>

          <div className="drawer-tabs" role="tablist">
            {(['overview', 'prompt', 'tools', 'guardrails'] as Tab[]).map(t => (
              <button
                key={t}
                role="tab"
                aria-selected={tab === t}
                className={`drawer-tab${tab === t ? ' active' : ''}`}
                onClick={() => setTab(t)}
              >
                {t === 'overview' && 'Overview'}
                {t === 'prompt' && 'System Prompt'}
                {t === 'tools' && `Tools (${agent.tools_observed.length})`}
                {t === 'guardrails' && `Guardrails (${guardrails.length})`}
              </button>
            ))}
          </div>

          <div className="drawer-body">
            {tab === 'overview' && (
              <dl className="kv-list">
                <div className="kv-row">
                  <dt>Agent ID</dt>
                  <dd className="mono">{agent.agent_id}</dd>
                </div>
                <div className="kv-row">
                  <dt>Framework</dt>
                  <dd>{agent.framework || '—'}</dd>
                </div>
                <div className="kv-row">
                  <dt>Role</dt>
                  <dd>{agent.role || '—'}</dd>
                </div>
                <div className="kv-row">
                  <dt>Model</dt>
                  <dd className="mono">{agent.model || '—'}</dd>
                </div>
                <div className="kv-row">
                  <dt>Distinct tools</dt>
                  <dd className="mono">{agent.tools_observed.length}</dd>
                </div>
                <div className="kv-row">
                  <dt>Total tool calls</dt>
                  <dd className="mono">{agent.total_tool_calls}</dd>
                </div>
                <div className="kv-row">
                  <dt>Run count</dt>
                  <dd className="mono">{agent.run_count}</dd>
                </div>
                <div className="kv-row">
                  <dt>Observations</dt>
                  <dd className="mono">{agent.observation_count}</dd>
                </div>
                <div className="kv-row">
                  <dt>First seen</dt>
                  <dd>{formatTime(agent.first_seen)}</dd>
                </div>
                <div className="kv-row">
                  <dt>Last seen</dt>
                  <dd>{formatTime(agent.last_seen)}</dd>
                </div>
              </dl>
            )}

            {tab === 'prompt' && (
              <div className="prompt-pane">
                {agent.system_prompt ? (
                  <>
                    <div className="prompt-pane-actions">
                      <button className="btn btn-sm btn-ghost" onClick={handleCopyPrompt}>
                        {copied ? '✓ Copied' : 'Copy prompt'}
                      </button>
                      {agent.system_prompt_hash && (
                        <span className="text-muted mono" style={{ fontSize: 'var(--text-xs, 11px)' }}>
                          {agent.system_prompt_hash.slice(0, 12)}
                        </span>
                      )}
                    </div>
                    <pre className="prompt-pane-body">{agent.system_prompt}</pre>
                  </>
                ) : (
                  <div className="empty-pane">
                    <p>This framework didn't emit a system prompt on its spans.</p>
                    <p className="text-muted">
                      For Strands: ensure <code>llm.system</code> is set on LLM spans.
                      For OpenClaw: enable <code>captureContent.systemPrompt</code> in the gateway config.
                    </p>
                  </div>
                )}
              </div>
            )}

            {tab === 'guardrails' && (
              <div className="guardrails-tab-list">
                {guardrailsLoading ? (
                  <div>
                    {[...Array(2)].map((_, i) => (
                      <div key={i} className="loading-skeleton" style={{ height: 110, marginBottom: 8 }} />
                    ))}
                  </div>
                ) : guardrails.length === 0 ? (
                  <div className="empty-pane">
                    <p>No guardrails registered for this agent.</p>
                    <p className="text-muted">
                      Wrap the agent with <code>register_guardrails(...)</code> in your SDK init to see them here.
                    </p>
                  </div>
                ) : (
                  guardrails.map(g => (
                    <GuardrailCard key={`${g.agent_id}/${g.guardrail_name}`} guardrail={g} />
                  ))
                )}
              </div>
            )}

            {tab === 'tools' && (
              <div>
                {toolsLoading ? (
                  <div>
                    {[...Array(3)].map((_, i) => (
                      <div key={i} className="loading-skeleton" style={{ height: 36, marginBottom: 4 }} />
                    ))}
                  </div>
                ) : tools.length === 0 ? (
                  <div className="empty-pane">
                    <p>No tool usage recorded for this agent.</p>
                  </div>
                ) : (
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Tool</th>
                        <th>Category</th>
                        <th>Calls</th>
                        <th>Errors</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tools.map(t => (
                        <tr key={t.tool_name}>
                          <td className="primary">{t.tool_name}</td>
                          <td><span className="badge">{t.tool_category}</span></td>
                          <td className="mono">{t.call_count}</td>
                          <td className="mono">
                            {t.error_count > 0 ? (
                              <span style={{ color: 'var(--risk-critical)' }}>{t.error_count}</span>
                            ) : '0'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </Drawer>
  )
}
