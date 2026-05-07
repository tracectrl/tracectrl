import { useState } from 'react'
import { AttackPath } from '../api/client'
import Drawer, { DrawerClose } from './shared/Drawer'

interface AttackFindingsPanelProps {
  paths: AttackPath[]
  selectedPath: AttackPath | null
  onPathSelect: (path: AttackPath | null) => void
  onClose: () => void
}

interface MitigationSuggestion {
  type: 'guardrail' | 'human_review' | 'input_validation' | 'access_control' | 'architecture'
  priority: 'high' | 'medium' | 'low'
  suggestion: string
  target?: string
}

type Tone = 'critical' | 'high' | 'medium' | 'low' | 'neutral'

function severityTone(severity: string): Tone {
  const s = severity.toUpperCase()
  if (s === 'CRITICAL') return 'critical'
  if (s === 'HIGH') return 'high'
  if (s === 'MEDIUM') return 'medium'
  if (s === 'LOW') return 'low'
  return 'neutral'
}

function formatTitle(title: string): string {
  return title
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function PathChain({ nodes }: { nodes: string[] }) {
  return (
    <>
      {nodes.map((node, i) => {
        let label = node
        if (node === 'external_input') label = 'External Input'
        else if (node.startsWith('tool:')) label = node.substring(5)
        else if (node.startsWith('ingress:')) label = node.substring(8)
        return (
          <span key={i}>
            {i > 0 && <span className="chain-arrow"> → </span>}
            <span className="chain-node">{label}</span>
          </span>
        )
      })}
    </>
  )
}

function generateMitigations(path: AttackPath): MitigationSuggestion[] {
  const suggestions: MitigationSuggestion[] = []
  const pathNodes = path.path_nodes || []

  const hasExternalIngress = pathNodes.some((n) => n.startsWith('ingress:'))
  if (hasExternalIngress) {
    const ingressNode = pathNodes.find((n) => n.startsWith('ingress:'))
    const ingressType = ingressNode?.split(':')[1] || 'external'
    suggestions.push({
      type: 'input_validation',
      priority: 'high',
      suggestion: `Add input validation and sanitization at ${ingressType} ingress point to detect and block malicious payloads`,
      target: ingressNode,
    })
  }

  const hasFinancialOps = pathNodes.some((n) => n.includes('payment') || n.includes('billing') || n.includes('financial'))
  if (hasFinancialOps) {
    suggestions.push({
      type: 'human_review',
      priority: 'high',
      suggestion: 'Require human-in-the-loop approval for all financial operations above a threshold',
      target: pathNodes.find((n) => n.includes('payment') || n.includes('billing')),
    })
  }

  const hasExfiltration = pathNodes.some((n) => n.includes('send_email') || n.includes('external_api'))
  if (hasExfiltration) {
    const exfilTool = pathNodes.find((n) => n.includes('send_email') || n.includes('external_api'))
    suggestions.push({
      type: 'access_control',
      priority: 'high',
      suggestion: 'Implement data loss prevention (DLP) controls to scan and block sensitive data from being exfiltrated',
      target: exfilTool,
    })
  }

  const hasCodeExec = pathNodes.some((n) => n.includes('execute') || n.includes('code_execution'))
  if (hasCodeExec) {
    suggestions.push({
      type: 'access_control',
      priority: 'high',
      suggestion: 'Disable code execution capabilities or sandbox the execution environment with strict permissions',
    })
  }

  const agentNodes = pathNodes.filter((n) => !n.startsWith('tool:') && !n.startsWith('ingress:'))
  if (agentNodes.length > 3) {
    suggestions.push({
      type: 'architecture',
      priority: 'medium',
      suggestion: `Reduce agent chain complexity (currently ${agentNodes.length} agents). Consolidate agents or add validation checkpoints between hops`,
    })
  }

  const hasCompromisedTool = pathNodes[0]?.startsWith('tool:')
  if (hasCompromisedTool) {
    const toolName = pathNodes[0]?.split(':')[1]
    suggestions.push({
      type: 'input_validation',
      priority: 'high',
      suggestion: `Validate and sanitize data from external tool "${toolName}" before processing. Consider the tool output as untrusted input`,
      target: pathNodes[0],
    })
  }

  const firstAgent = agentNodes[0]
  if (firstAgent && hasExternalIngress) {
    suggestions.push({
      type: 'guardrail',
      priority: 'high',
      suggestion: `Add prompt injection detection guardrails for agent "${firstAgent}" to filter malicious instructions`,
      target: firstAgent,
    })
  }

  suggestions.push({
    type: 'guardrail',
    priority: 'low',
    suggestion: 'Enable real-time monitoring and alerting for suspicious patterns in this attack path',
  })

  return suggestions
}

export default function AttackFindingsPanel({ paths, selectedPath, onPathSelect, onClose }: AttackFindingsPanelProps) {
  const [expandedMitigation, setExpandedMitigation] = useState<string | null>(null)

  return (
    <Drawer
      open
      onClose={onClose}
      ariaLabel="Attack surface findings"
      tone={selectedPath ? severityTone(selectedPath.severity) : 'neutral'}
      widthPx={520}
    >
      <header className="drawer-header">
        <h3 className="drawer-title" style={{ margin: 0 }}>Attack Surface Findings</h3>
        <div style={{ marginLeft: 'auto' }}>
          <DrawerClose onClose={onClose} />
        </div>
      </header>

      <div className="drawer-body">
        {paths.length === 0 ? (
          <p className="panel-muted" style={{ textAlign: 'center', padding: '24px 0' }}>
            No attack paths detected
          </p>
        ) : (
          <div className="attack-drawer-list">
            {paths.map((path) => {
              const isSelected = selectedPath?.path_id === path.path_id
              const tone = severityTone(path.severity)
              const showMit = expandedMitigation === path.path_id
              return (
                <div
                  key={path.path_id}
                  className={`attack-card${isSelected ? ' is-selected' : ''}`}
                  role="button"
                  tabIndex={0}
                  aria-pressed={isSelected}
                  onClick={() => onPathSelect(isSelected ? null : path)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onPathSelect(isSelected ? null : path)
                    }
                  }}
                >
                  <div className="attack-card-top">
                    <span className={`attack-severity-pill pill-${tone}`}>
                      {path.severity}
                    </span>
                  </div>

                  <h4 className="attack-card-title">{formatTitle(path.title)}</h4>

                  <div className="attack-card-chain">
                    <PathChain nodes={path.path_nodes} />
                  </div>

                  <div className="attack-card-metarow">
                    <div className="attack-card-risk">
                      Risk Score: <strong>{path.risk_score.toFixed(1)}</strong>
                    </div>
                    <button
                      type="button"
                      className="attack-mitigate-btn"
                      onClick={(e) => {
                        e.stopPropagation()
                        setExpandedMitigation(showMit ? null : path.path_id)
                      }}
                    >
                      {showMit ? 'Hide' : 'Mitigate'}
                    </button>
                  </div>

                  <p className="attack-card-desc">{path.description}</p>

                  {showMit && (
                    <div className="attack-mitigations">
                      <div className="attack-mitigations-h">Mitigation Suggestions</div>
                      {generateMitigations(path).map((m, idx) => (
                        <div key={idx} className="attack-mitigation-item">
                          <div>
                            <span className="attack-mit-type">{m.type.replace('_', ' ')}</span>
                            <span className={`attack-mit-pri pri-${m.priority}`}>{m.priority}</span>
                          </div>
                          <div className="attack-mit-text">{m.suggestion}</div>
                          {m.target && <div className="attack-mit-target">Target: {m.target}</div>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </Drawer>
  )
}
