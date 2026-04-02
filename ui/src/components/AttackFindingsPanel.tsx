import { CSSProperties } from 'react'
import { AttackPath } from '../api/client'

interface AttackFindingsPanelProps {
  paths: AttackPath[]
  onClose: () => void
}

export default function AttackFindingsPanel({ paths, onClose }: AttackFindingsPanelProps) {
  const severityColor = (severity: string): string => {
    switch (severity) {
      case 'CRITICAL': return '#EF4444'
      case 'HIGH': return '#F97316'
      case 'MEDIUM': return '#EAB308'
      case 'LOW': return '#10B981'
      default: return '#6B7280'
    }
  }

  const formatPathChain = (pathNodes: string[]) => {
    return pathNodes.map((node, i) => {
      let label = node
      if (node === 'external_input') {
        label = 'External Input'
      } else if (node.startsWith('tool:')) {
        label = node.substring(5)
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

  const findingCardStyle: CSSProperties = {
    background: 'rgba(255, 255, 255, 0.02)',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '8px',
    padding: '16px',
  }

  const findingHeaderStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '8px',
  }

  const owaspTagStyle: CSSProperties = {
    fontSize: '11px',
    color: '#9CA3AF',
    fontFamily: "'JetBrains Mono', monospace",
  }

  const findingTitleStyle: CSSProperties = {
    fontSize: '14px',
    fontWeight: 600,
    color: '#F5F5F5',
    margin: '8px 0',
  }

  const pathChainStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '4px',
    margin: '12px 0',
    padding: '8px',
    background: 'rgba(0, 0, 0, 0.2)',
    borderRadius: '4px',
    fontSize: '12px',
    fontFamily: "'JetBrains Mono', monospace",
  }

  const riskScoreStyle: CSSProperties = {
    fontSize: '12px',
    color: '#9CA3AF',
    margin: '8px 0',
  }

  const riskScoreValueStyle: CSSProperties = {
    color: '#F97316',
    fontSize: '14px',
  }

  const findingDescriptionStyle: CSSProperties = {
    fontSize: '13px',
    lineHeight: 1.5,
    color: '#D1D5DB',
    marginTop: '8px',
  }

  const emptyStateStyle: CSSProperties = {
    textAlign: 'center',
    color: '#6B7280',
    padding: '32px 16px',
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
          {paths.map((path) => (
            <div key={path.path_id} style={findingCardStyle}>
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
                <span style={owaspTagStyle}>{path.owasp_tag}</span>
              </div>

              <h4 style={findingTitleStyle}>{path.title}</h4>

              <div style={pathChainStyle}>
                {formatPathChain(path.path_nodes)}
              </div>

              <div style={riskScoreStyle}>
                Risk Score: <strong style={riskScoreValueStyle}>{path.risk_score.toFixed(1)}</strong>
              </div>

              <p style={findingDescriptionStyle}>{path.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
