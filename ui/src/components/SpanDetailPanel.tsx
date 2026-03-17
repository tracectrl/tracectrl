import { SpanDetail, formatDuration } from '../api/sessions'

interface SpanDetailPanelProps {
  span: SpanDetail | null
  onClose: () => void
}

function getSpanType(span: SpanDetail): string {
  return span.attributes['openinference.span.kind']
    || span.attributes['oi.span_kind']
    || span.span_kind
    || 'INTERNAL'
}

function formatTimestamp(ns: number): string {
  return new Date(ns / 1_000_000).toLocaleString()
}

function groupAttributes(attrs: Record<string, string>): { label: string; entries: [string, string][] }[] {
  const groups: Record<string, [string, string][]> = {
    'TraceCtrl': [],
    'Input / Output': [],
    'OpenInference': [],
    'Other': [],
  }

  for (const [key, value] of Object.entries(attrs)) {
    if (!value) continue
    if (key.startsWith('tracectrl.')) groups['TraceCtrl'].push([key, value])
    else if (key.startsWith('input.') || key.startsWith('output.')) groups['Input / Output'].push([key, value])
    else if (key.startsWith('openinference.') || key.startsWith('oi.')) groups['OpenInference'].push([key, value])
    else groups['Other'].push([key, value])
  }

  return Object.entries(groups)
    .filter(([, entries]) => entries.length > 0)
    .map(([label, entries]) => ({ label, entries }))
}

export default function SpanDetailPanel({ span, onClose }: SpanDetailPanelProps) {
  if (!span) return null

  const type = getSpanType(span)
  const isError = span.status_code === 'STATUS_CODE_ERROR'
  const inputValue = span.attributes['input.value']
  const outputValue = span.attributes['output.value']
  const attrGroups = groupAttributes(span.attributes)
  const resourceEntries = Object.entries(span.resource_attributes).filter(([, v]) => v)

  return (
    <div className={`detail-panel open`}>
      <div className="detail-panel-header">
        <h3 title={span.span_name}>{span.span_name}</h3>
        <button className="detail-panel-close" onClick={onClose}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M1 1l12 12M13 1L1 13" />
          </svg>
        </button>
      </div>

      {/* Type + Status badges */}
      <div className="flex gap-2 mb-4">
        <span className={`badge badge-${type.toLowerCase()}`}>{type}</span>
        <span className={`badge ${isError ? 'badge-critical' : 'badge-low'}`}>
          {isError ? 'ERROR' : 'OK'}
        </span>
      </div>

      {/* Timing */}
      <div className="kv-list mb-4">
        <div className="kv-item">
          <div className="kv-key">Duration</div>
          <div className="kv-value mono">{formatDuration(span.duration_ns)}</div>
        </div>
        <div className="kv-item">
          <div className="kv-key">Start Time</div>
          <div className="kv-value mono">{formatTimestamp(span.start_ns)}</div>
        </div>
        <div className="kv-item">
          <div className="kv-key">Service</div>
          <div className="kv-value">{span.service_name || 'unknown'}</div>
        </div>
        <div className="kv-item">
          <div className="kv-key">Span ID</div>
          <div className="kv-value mono">{span.span_id}</div>
        </div>
        {span.status_message && (
          <div className="kv-item">
            <div className="kv-key">Status Message</div>
            <div className="kv-value" style={{ color: isError ? 'var(--risk-critical)' : undefined }}>
              {span.status_message}
            </div>
          </div>
        )}
      </div>

      {/* Input / Output blocks */}
      {inputValue && (
        <div className="span-io-block mb-4">
          <div className="kv-key">Input</div>
          <pre className="span-io-content">{inputValue}</pre>
        </div>
      )}
      {outputValue && (
        <div className="span-io-block mb-4">
          <div className="kv-key">Output</div>
          <pre className="span-io-content">{outputValue}</pre>
        </div>
      )}

      {/* Grouped attributes */}
      {attrGroups.map(group => (
        <div key={group.label} className="mb-4">
          <div className="detail-section-label">{group.label}</div>
          <div className="kv-list">
            {group.entries.map(([key, value]) => (
              <div key={key} className="kv-item">
                <div className="kv-key">{key}</div>
                <div className="kv-value mono">{value}</div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Resource attributes (collapsed by default via <details>) */}
      {resourceEntries.length > 0 && (
        <details className="span-resource-details">
          <summary className="detail-section-label" style={{ cursor: 'pointer' }}>
            Resource Attributes ({resourceEntries.length})
          </summary>
          <div className="kv-list mt-2">
            {resourceEntries.map(([key, value]) => (
              <div key={key} className="kv-item">
                <div className="kv-key">{key}</div>
                <div className="kv-value mono">{value}</div>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}
