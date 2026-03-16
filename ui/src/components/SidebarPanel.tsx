import { TopologyNode } from '../api/client'

interface SidebarPanelProps {
  node: TopologyNode | null
  onClose: () => void
}

export default function SidebarPanel({ node, onClose }: SidebarPanelProps) {
  return (
    <div className={`detail-panel${node ? ' open' : ''}`}>
      {node && (
        <>
          <div className="detail-panel-header">
            <h3>{node.label}</h3>
            <button className="detail-panel-close" onClick={onClose} aria-label="Close panel">
              &times;
            </button>
          </div>

          <div className="flex items-center gap-2 mb-4">
            <span className={node.type === 'agent' ? 'badge badge-agent' : 'badge badge-tool'}>
              {node.type}
            </span>
            {node.metadata.maturity != null && (
              <span className={`badge badge-${String(node.metadata.maturity).toLowerCase()}`}>
                {String(node.metadata.maturity)}
              </span>
            )}
          </div>

          <div className="kv-list">
            {Object.entries(node.metadata).map(([key, value]) => {
              const display = Array.isArray(value)
                ? (value.length > 0 ? value.join(', ') : null)
                : (value != null && String(value) !== '' ? String(value) : null)
              return (
                <div className="kv-item" key={key}>
                  <div className="kv-key">{key.replace(/_/g, ' ')}</div>
                  <div className={`kv-value${display ? ' mono' : ''}`}>
                    {display ?? <span className="detail-field-value empty">—</span>}
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
