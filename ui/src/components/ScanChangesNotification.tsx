import { useEffect, useState } from 'react'
import { ScanDiff } from '../utils/scanDiff'

interface Props {
  diff: ScanDiff | null
  onClose: () => void
}

// Format property values for display
function formatValue(value: unknown): string {
  if (value === undefined || value === null) return 'none'
  if (typeof value === 'boolean') return value ? 'enabled' : 'disabled'
  if (Array.isArray(value)) {
    if (value.length === 0) return 'none'
    if (value.length <= 2) return value.join(', ')
    return `${value.slice(0, 2).join(', ')}, +${value.length - 2} more`
  }
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

// Format property names for display
function formatPropertyName(property: string): string {
  return property
    .replace(/_/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

export default function ScanChangesNotification({ diff, onClose }: Props) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (diff?.hasChanges) {
      setVisible(true)
      // Auto-dismiss after 15 seconds
      const timer = setTimeout(() => {
        setVisible(false)
        setTimeout(onClose, 300) // Wait for fade-out animation
      }, 15000)
      return () => clearTimeout(timer)
    }
  }, [diff, onClose])

  if (!diff?.hasChanges) return null

  const handleClose = () => {
    setVisible(false)
    setTimeout(onClose, 300)
  }

  const addedNodes = diff.nodeChanges.filter(c => c.type === 'added')
  const removedNodes = diff.nodeChanges.filter(c => c.type === 'removed')
  const modifiedNodes = diff.nodeChanges.filter(c => c.type === 'modified')

  return (
    <div className={`scan-changes-notification${visible ? ' visible' : ''}`}>
      <div className="scan-changes-header">
        <div className="scan-changes-title">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M8 1v14M1 8h14" />
          </svg>
          Scan Changes Detected
        </div>
        <button className="scan-changes-close" onClick={handleClose} aria-label="Close">×</button>
      </div>

      <div className="scan-changes-body">
        {/* Vulnerability changes */}
        {diff.totalVulnDelta !== 0 && (
          <div className="scan-change-section">
            <div className="scan-change-section-title">Security Findings</div>
            <div className={`scan-change-vuln ${diff.totalVulnDelta > 0 ? 'worse' : 'better'}`}>
              {diff.totalVulnDelta > 0 ? (
                <span className="scan-change-vuln-icon">⚠️</span>
              ) : (
                <span className="scan-change-vuln-icon">✓</span>
              )}
              <span>
                {Math.abs(diff.totalVulnDelta)} {Math.abs(diff.totalVulnDelta) === 1 ? 'finding' : 'findings'}{' '}
                {diff.totalVulnDelta > 0 ? 'added' : 'resolved'}
              </span>
            </div>
            {(diff.vulnerabilityChanges.critical !== 0 ||
              diff.vulnerabilityChanges.high !== 0 ||
              diff.vulnerabilityChanges.medium !== 0) && (
              <div className="scan-change-vuln-breakdown">
                {diff.vulnerabilityChanges.critical !== 0 && (
                  <span className="scan-vuln-delta critical">
                    {diff.vulnerabilityChanges.critical > 0 ? '+' : ''}
                    {diff.vulnerabilityChanges.critical} critical
                  </span>
                )}
                {diff.vulnerabilityChanges.high !== 0 && (
                  <span className="scan-vuln-delta high">
                    {diff.vulnerabilityChanges.high > 0 ? '+' : ''}
                    {diff.vulnerabilityChanges.high} high
                  </span>
                )}
                {diff.vulnerabilityChanges.medium !== 0 && (
                  <span className="scan-vuln-delta medium">
                    {diff.vulnerabilityChanges.medium > 0 ? '+' : ''}
                    {diff.vulnerabilityChanges.medium} medium
                  </span>
                )}
              </div>
            )}

            {/* Show individual finding changes */}
            {diff.findingChanges.length > 0 && (
              <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {diff.findingChanges.slice(0, 5).map(finding => (
                  <div
                    key={finding.checkId}
                    className="scan-change-finding"
                    style={{
                      fontSize: '11px',
                      color: 'var(--gray-400)',
                      paddingLeft: '8px',
                      borderLeft: `2px solid ${
                        finding.type === 'added'
                          ? finding.severity === 'critical' ? '#FF4D4D'
                          : finding.severity === 'high' ? '#FF6B35'
                          : '#FFBB00'
                          : '#22C55E'
                      }`,
                    }}
                  >
                    {finding.type === 'added' ? '+ ' : '✓ '}
                    {finding.title}
                  </div>
                ))}
                {diff.findingChanges.length > 5 && (
                  <div style={{ fontSize: '10px', color: 'var(--gray-600)', paddingLeft: '8px' }}>
                    +{diff.findingChanges.length - 5} more...
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Added nodes */}
        {addedNodes.length > 0 && (
          <div className="scan-change-section">
            <div className="scan-change-section-title">New Components</div>
            {addedNodes.map(node => (
              <div key={node.nodeId} className="scan-change-item added">
                <span className="scan-change-icon">+</span>
                <span className="scan-change-label">{node.label}</span>
              </div>
            ))}
          </div>
        )}

        {/* Removed nodes */}
        {removedNodes.length > 0 && (
          <div className="scan-change-section">
            <div className="scan-change-section-title">Removed Components</div>
            {removedNodes.map(node => (
              <div key={node.nodeId} className="scan-change-item removed">
                <span className="scan-change-icon">−</span>
                <span className="scan-change-label">{node.label}</span>
              </div>
            ))}
          </div>
        )}

        {/* Modified nodes */}
        {modifiedNodes.length > 0 && (
          <div className="scan-change-section">
            <div className="scan-change-section-title">Configuration Changes</div>
            {modifiedNodes.map(node => (
              <div key={`${node.nodeId}-${node.property}`} className="scan-change-item modified">
                <span className="scan-change-icon">~</span>
                <div className="scan-change-detail">
                  <div className="scan-change-label">{node.label}</div>
                  <div className="scan-change-property">
                    {formatPropertyName(node.property || '')}: <span className="old-value">{formatValue(node.oldValue)}</span> →{' '}
                    <span className="new-value">{formatValue(node.newValue)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
