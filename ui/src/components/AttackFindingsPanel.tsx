import { CSSProperties, useState } from 'react'
import { AttackPath } from '../api/client'

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

export default function AttackFindingsPanel({ paths, selectedPath, onPathSelect, onClose }: AttackFindingsPanelProps) {
  const [expandedMitigation, setExpandedMitigation] = useState<string | null>(null)

  const severityColor = (severity: string): string => {
    switch (severity) {
      case 'CRITICAL': return '#EF4444'
      case 'HIGH': return '#F97316'
      case 'MEDIUM': return '#EAB308'
      case 'LOW': return '#10B981'
      default: return '#6B7280'
    }
  }

  const generateMitigations = (path: AttackPath): MitigationSuggestion[] => {
    const suggestions: MitigationSuggestion[] = []
    const pathNodes = path.path_nodes || []
    const pathSteps = path.path_steps || []
    const agentsInvolved = path.agents_involved || []

    // Check if path starts with ingress (external input)
    const hasExternalIngress = pathNodes.some(node => node.startsWith('ingress:'))
    if (hasExternalIngress) {
      const ingressNode = pathNodes.find(node => node.startsWith('ingress:'))
      const ingressType = ingressNode?.split(':')[1] || 'external'
      suggestions.push({
        type: 'input_validation',
        priority: 'high',
        suggestion: `Add input validation and sanitization at ${ingressType} ingress point to detect and block malicious payloads`,
        target: ingressNode,
      })
    }

    // Check for financial/payment operations
    const hasFinancialOps = pathSteps.some(step =>
      step.vulnerability?.includes('financial') ||
      step.node_id?.includes('payment') ||
      step.node_id?.includes('billing')
    )
    if (hasFinancialOps) {
      suggestions.push({
        type: 'human_review',
        priority: 'high',
        suggestion: 'Require human-in-the-loop approval for all financial operations above a threshold',
        target: pathSteps.find(s => s.node_id?.includes('payment') || s.node_id?.includes('billing'))?.node_id,
      })
    }

    // Check for data exfiltration (email, external API)
    const hasExfiltration = pathNodes.some(node =>
      node.includes('send_email') ||
      node.includes('external_api')
    )
    if (hasExfiltration) {
      const exfilTool = pathNodes.find(n => n.includes('send_email') || n.includes('external_api'))
      suggestions.push({
        type: 'access_control',
        priority: 'high',
        suggestion: 'Implement data loss prevention (DLP) controls to scan and block sensitive data from being exfiltrated',
        target: exfilTool,
      })
    }

    // Check for code execution
    const hasCodeExec = pathNodes.some(node =>
      node.includes('execute') ||
      node.includes('code_execution')
    )
    if (hasCodeExec) {
      suggestions.push({
        type: 'access_control',
        priority: 'high',
        suggestion: 'Disable code execution capabilities or sandbox the execution environment with strict permissions',
      })
    }

    // Long attack chains (> 3 agents)
    if (agentsInvolved.length > 3) {
      suggestions.push({
        type: 'architecture',
        priority: 'medium',
        suggestion: `Reduce agent chain complexity (currently ${agentsInvolved.length} agents). Consolidate agents or add validation checkpoints between hops`,
      })
    }

    // Check for compromised tools (tool as source)
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

    // Add guardrails for prompt injection
    const firstAgent = agentsInvolved[0]
    if (firstAgent && hasExternalIngress) {
      suggestions.push({
        type: 'guardrail',
        priority: 'high',
        suggestion: `Add prompt injection detection guardrails for agent "${firstAgent}" to filter malicious instructions`,
        target: firstAgent,
      })
    }

    // General: add monitoring
    suggestions.push({
      type: 'guardrail',
      priority: 'low',
      suggestion: 'Enable real-time monitoring and alerting for suspicious patterns in this attack path',
    })

    return suggestions
  }

  const formatTitle = (title: string): string => {
    // Replace underscores with spaces and convert to proper case
    return title
      .replace(/_/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, (char) => char.toUpperCase())
  }

  const formatPathChain = (pathNodes: string[]) => {
    return pathNodes.map((node, i) => {
      let label = node
      if (node === 'external_input') {
        label = 'External Input'
      } else if (node.startsWith('tool:')) {
        label = node.substring(5)
      } else if (node.startsWith('ingress:')) {
        label = node.substring(8)
      }

      const arrowStyle: CSSProperties = {
        color: '#6B7280',
        fontWeight: 'bold',
      }

      const nodeStyle: CSSProperties = {
        color: '#60A5FA',
      }

      return (
        <span key={i}>
          {i > 0 && <span style={arrowStyle}> → </span>}
          <span style={nodeStyle}>{label}</span>
        </span>
      )
    })
  }

  const findingsListStyle: CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  }

  const findingCardStyle = (isSelected: boolean): CSSProperties => ({
    background: isSelected ? 'rgba(239, 68, 68, 0.1)' : 'rgba(255, 255, 255, 0.02)',
    border: isSelected ? '2px solid #EF4444' : '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '8px',
    padding: '16px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    overflow: 'hidden',
  })

  const findingHeaderStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '12px',
    flexWrap: 'wrap',
    gap: '8px',
  }

  const findingTitleStyle: CSSProperties = {
    fontSize: '13px',
    fontWeight: 600,
    color: '#F5F5F5',
    margin: '0 0 12px 0',
    lineHeight: 1.4,
    wordBreak: 'break-word',
    overflowWrap: 'break-word',
  }

  const pathChainStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '4px',
    margin: '0 0 12px 0',
    padding: '10px',
    background: 'rgba(0, 0, 0, 0.3)',
    borderRadius: '6px',
    fontSize: '11px',
    fontFamily: "'JetBrains Mono', monospace",
    lineHeight: 1.6,
  }

  const riskScoreStyle: CSSProperties = {
    fontSize: '12px',
    color: '#9CA3AF',
    margin: '0 0 10px 0',
  }

  const riskScoreValueStyle: CSSProperties = {
    color: '#F97316',
    fontSize: '14px',
    fontWeight: 600,
  }

  const findingDescriptionStyle: CSSProperties = {
    fontSize: '12px',
    lineHeight: 1.6,
    color: '#D1D5DB',
    marginTop: '0',
    wordBreak: 'break-word',
    overflowWrap: 'break-word',
  }

  const emptyStateStyle: CSSProperties = {
    textAlign: 'center',
    color: '#6B7280',
    padding: '32px 16px',
  }

  const mitigateButtonStyle: CSSProperties = {
    fontSize: '11px',
    padding: '4px 10px',
    background: 'rgba(59, 130, 246, 0.1)',
    border: '1px solid rgba(59, 130, 246, 0.3)',
    borderRadius: '4px',
    color: '#60A5FA',
    cursor: 'pointer',
    fontWeight: 600,
    transition: 'all 0.2s ease',
  }

  const mitigationSectionStyle: CSSProperties = {
    marginTop: '12px',
    padding: '12px',
    background: 'rgba(0, 0, 0, 0.3)',
    borderRadius: '6px',
    borderLeft: '3px solid #60A5FA',
  }

  const mitigationHeaderStyle: CSSProperties = {
    fontSize: '12px',
    fontWeight: 600,
    color: '#60A5FA',
    marginBottom: '10px',
  }

  const mitigationItemStyle: CSSProperties = {
    marginBottom: '10px',
    paddingBottom: '10px',
    borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
  }

  const mitigationTypeStyle = (type: string): CSSProperties => {
    const colors = {
      guardrail: '#8B5CF6',
      human_review: '#F59E0B',
      input_validation: '#10B981',
      access_control: '#EF4444',
      architecture: '#6B7280',
    }
    return {
      display: 'inline-block',
      fontSize: '9px',
      padding: '2px 6px',
      borderRadius: '3px',
      background: colors[type as keyof typeof colors] || '#6B7280',
      color: '#fff',
      fontWeight: 600,
      textTransform: 'uppercase',
      marginRight: '8px',
    }
  }

  const mitigationPriorityStyle = (priority: string): CSSProperties => {
    const colors = {
      high: '#EF4444',
      medium: '#F59E0B',
      low: '#6B7280',
    }
    return {
      display: 'inline-block',
      fontSize: '9px',
      padding: '2px 6px',
      borderRadius: '3px',
      background: colors[priority as keyof typeof colors] || '#6B7280',
      color: '#fff',
      fontWeight: 600,
      textTransform: 'uppercase',
    }
  }

  const mitigationTextStyle: CSSProperties = {
    fontSize: '12px',
    lineHeight: 1.5,
    color: '#D1D5DB',
    marginTop: '6px',
  }

  const mitigationTargetStyle: CSSProperties = {
    fontSize: '10px',
    color: '#9CA3AF',
    fontFamily: "'JetBrains Mono', monospace",
    marginTop: '4px',
  }

  return (
    <div className="detail-panel open">
      <div className="detail-panel-header">
        <h3>Attack Surface Findings</h3>
        <button className="detail-panel-close" onClick={onClose} aria-label="Close panel">
          &times;
        </button>
      </div>

      {paths.length === 0 ? (
        <div style={emptyStateStyle}>No attack paths detected</div>
      ) : (
        <div style={findingsListStyle}>
          {paths.map((path) => {
            const isSelected = selectedPath?.path_id === path.path_id
            return (
            <div
              key={path.path_id}
              style={findingCardStyle(isSelected)}
              onClick={() => onPathSelect(isSelected ? null : path)}
            >
              <div style={findingHeaderStyle}>
                <span
                  style={{
                    backgroundColor: severityColor(path.severity),
                    color: '#fff',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 600,
                  }}
                >
                  {path.severity}
                </span>
              </div>

              <h4 style={findingTitleStyle}>{formatTitle(path.title)}</h4>

              <div style={pathChainStyle}>
                {formatPathChain(path.path_nodes)}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <div style={riskScoreStyle}>
                  Risk Score: <strong style={riskScoreValueStyle}>{path.risk_score.toFixed(1)}</strong>
                </div>
                <button
                  style={mitigateButtonStyle}
                  onClick={(e) => {
                    e.stopPropagation()
                    setExpandedMitigation(expandedMitigation === path.path_id ? null : path.path_id)
                  }}
                  onMouseEnter={(e) => {
                    (e.target as HTMLButtonElement).style.background = 'rgba(59, 130, 246, 0.2)'
                  }}
                  onMouseLeave={(e) => {
                    (e.target as HTMLButtonElement).style.background = 'rgba(59, 130, 246, 0.1)'
                  }}
                >
                  {expandedMitigation === path.path_id ? 'Hide' : 'Mitigate'}
                </button>
              </div>

              <p style={findingDescriptionStyle}>{path.description}</p>

              {expandedMitigation === path.path_id && (
                <div style={mitigationSectionStyle}>
                  <div style={mitigationHeaderStyle}>Mitigation Suggestions</div>
                  {generateMitigations(path).map((mitigation, idx) => (
                    <div key={idx} style={mitigationItemStyle}>
                      <div>
                        <span style={mitigationTypeStyle(mitigation.type)}>
                          {mitigation.type.replace('_', ' ')}
                        </span>
                        <span style={mitigationPriorityStyle(mitigation.priority)}>
                          {mitigation.priority}
                        </span>
                      </div>
                      <div style={mitigationTextStyle}>{mitigation.suggestion}</div>
                      {mitigation.target && (
                        <div style={mitigationTargetStyle}>Target: {mitigation.target}</div>
                      )}
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
  )
}
