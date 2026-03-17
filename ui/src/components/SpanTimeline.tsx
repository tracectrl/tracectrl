import { useMemo, useState } from 'react'
import { SpanDetail, formatDuration } from '../api/sessions'
import { buildTree, getSpanType, getSpanColor, SpanNode } from '../lib/spanUtils'

interface SpanTimelineProps {
  spans: SpanDetail[]
  traceDurationNs: number
  traceStartNs: number
  selectedSpanId: string | null
  onSpanSelect: (span: SpanDetail) => void
  /** When true, show the summary section above the timeline (used in Sessions inline) */
  compact?: boolean
}

interface TimelineRow {
  span: SpanNode
  kind: string
  indent: number
  isAgent: boolean
}

interface TraceSummary {
  agentName: string
  model: string
  totalDuration: number
  toolCalls: { name: string; count: number }[]
  llmCalls: number
  llmModel: string
}

function buildSummary(spans: SpanDetail[]): TraceSummary {
  let agentName = ''
  let model = ''
  let totalDuration = 0
  const toolMap = new Map<string, number>()
  let llmCalls = 0
  let llmModel = ''

  for (const span of spans) {
    const kind = getSpanType(span).toUpperCase()
    if (kind === 'AGENT') {
      if (!agentName) agentName = span.attributes['agent.name'] || span.span_name
      if (span.duration_ns > totalDuration) totalDuration = span.duration_ns
    }
    if (kind === 'TOOL') {
      const name = span.span_name
      toolMap.set(name, (toolMap.get(name) || 0) + 1)
    }
    if (kind === 'LLM') {
      llmCalls++
      if (!llmModel) {
        llmModel = span.attributes['llm.model_name']
          || span.attributes['gen_ai.response.model']
          || span.attributes['llm.model']
          || ''
      }
    }
    if (!model) {
      model = span.attributes['llm.model_name']
        || span.attributes['gen_ai.response.model']
        || span.attributes['llm.model']
        || ''
    }
  }

  const toolCalls = Array.from(toolMap.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)

  return { agentName, model, totalDuration, toolCalls, llmCalls, llmModel: llmModel || model }
}

export default function SpanTimeline({ spans, traceDurationNs, traceStartNs, selectedSpanId, onSpanSelect, compact }: SpanTimelineProps) {
  const [hoveredSpan, setHoveredSpan] = useState<{ span: SpanDetail; x: number; y: number } | null>(null)

  const rows = useMemo(() => {
    const roots = buildTree(spans)
    const result: TimelineRow[] = []

    function collectRows(nodes: SpanNode[], indent: number) {
      for (const node of nodes) {
        const kind = getSpanType(node).toUpperCase()
        if (kind === 'AGENT') {
          result.push({ span: node, kind, indent, isAgent: true })
          // Add direct children on separate rows, indented
          for (const child of node.children) {
            const childKind = getSpanType(child).toUpperCase()
            result.push({ span: child, kind: childKind, indent: indent + 1, isAgent: false })
            // If a child (e.g. TOOL) itself has children, recurse agents only
            collectRows(child.children.filter(c => getSpanType(c).toUpperCase() === 'AGENT'), indent + 1)
          }
          // Recurse into nested agents
          collectRows(node.children.filter(c => getSpanType(c).toUpperCase() === 'AGENT'), indent + 1)
        } else {
          // Non-agent root spans — still show them
          result.push({ span: node, kind, indent, isAgent: false })
          collectRows(node.children, indent)
        }
      }
    }
    collectRows(roots, 0)
    return result
  }, [spans])

  const summary = useMemo(() => buildSummary(spans), [spans])

  const pct = (ns: number) => traceDurationNs > 0 ? ((ns - traceStartNs) / traceDurationNs) * 100 : 0
  const widthPct = (ns: number) => traceDurationNs > 0 ? (ns / traceDurationNs) * 100 : 0

  // Time axis ticks
  const ticks = useMemo(() => {
    const count = 6
    const result = []
    for (let i = 0; i <= count; i++) {
      const ns = (traceDurationNs / count) * i
      result.push({ pct: (i / count) * 100, label: formatDuration(ns) })
    }
    return result
  }, [traceDurationNs])

  if (rows.length === 0) {
    return (
      <div className="empty-state" style={{ minHeight: 200 }}>
        <p className="text-muted">No agent spans found in this trace</p>
      </div>
    )
  }

  return (
    <div className="timeline-container" style={{ position: 'relative' }}>
      {/* Summary section — only in compact/inline mode */}
      {compact && (
        <div className="tl-summary">
          <div className="tl-summary-header">
            <div className="tl-summary-agent">
              <span className="tl-summary-agent-name">{summary.agentName || 'Unknown Agent'}</span>
              {summary.llmModel && (
                <span className="tl-summary-model">{summary.llmModel}</span>
              )}
              <span className="tl-summary-duration">{formatDuration(summary.totalDuration)}</span>
            </div>
          </div>
          <div className="tl-summary-details">
            {summary.toolCalls.length > 0 && (
              <div className="tl-summary-row">
                <span className="tl-summary-label">Tools</span>
                <span className="tl-summary-value">
                  {summary.toolCalls.map((t, i) => (
                    <span key={t.name} className="tl-tool-chip">
                      {t.name}{t.count > 1 ? ` \u00d7${t.count}` : ''}
                      {i < summary.toolCalls.length - 1 ? '' : ''}
                    </span>
                  ))}
                </span>
              </div>
            )}
            {summary.llmCalls > 0 && (
              <div className="tl-summary-row">
                <span className="tl-summary-label">LLM</span>
                <span className="tl-summary-value">
                  <span className="tl-llm-chip">{summary.llmCalls} call{summary.llmCalls !== 1 ? 's' : ''}{summary.llmModel ? ` \u00b7 ${summary.llmModel}` : ''}</span>
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Color key */}
      <div className="tl-color-key">
        <span className="tl-key-item"><span className="tl-key-dot" style={{ background: getSpanColor('AGENT') }} />Agent</span>
        <span className="tl-key-item"><span className="tl-key-dot" style={{ background: getSpanColor('TOOL') }} />Tool</span>
        <span className="tl-key-item"><span className="tl-key-dot" style={{ background: getSpanColor('LLM') }} />LLM</span>
      </div>

      {/* Time axis */}
      <div className="timeline-ruler">
        <div className="timeline-ruler-label-spacer" />
        <div className="timeline-ruler-track">
          {ticks.map((tick, i) => (
            <span key={i} className="timeline-tick" style={{ left: `${tick.pct}%` }}>
              {tick.label}
            </span>
          ))}
        </div>
      </div>

      {/* Timeline rows */}
      {rows.map(row => {
        const barLeft = Math.max(0, pct(row.span.start_ns))
        const barWidth = Math.max(0.5, widthPct(row.span.duration_ns))
        const barColor = getSpanColor(row.kind)
        const isSelected = selectedSpanId === row.span.span_id
        const labelText = row.span.span_name
        // Show inline label if bar is wide enough (> 8%)
        const showInlineLabel = barWidth > 8

        return (
          <div
            key={row.span.span_id}
            className={`tl-row${row.isAgent ? ' tl-row-agent' : ' tl-row-child'}`}
          >
            <div
              className="tl-row-label"
              style={{ paddingLeft: `${12 + row.indent * 16}px` }}
              title={row.span.span_name}
            >
              {row.isAgent ? (
                <span className="badge badge-agent" style={{ fontSize: 9, marginRight: 6 }}>AGENT</span>
              ) : (
                <span className={`badge badge-${row.kind.toLowerCase()}`} style={{ fontSize: 9, marginRight: 6 }}>{row.kind}</span>
              )}
              <span className="tl-row-label-text">{labelText}</span>
            </div>
            <div className="tl-row-track">
              <div
                className={`tl-bar${isSelected ? ' selected' : ''}`}
                style={{
                  left: `${barLeft}%`,
                  width: `${barWidth}%`,
                  backgroundColor: barColor,
                  height: row.isAgent ? '18px' : '14px',
                }}
                onClick={() => onSpanSelect(row.span)}
                onMouseEnter={e => setHoveredSpan({ span: row.span, x: e.clientX, y: e.clientY })}
                onMouseLeave={() => setHoveredSpan(null)}
              >
                {showInlineLabel && (
                  <span className="tl-bar-label">{labelText}</span>
                )}
              </div>
              <span
                className="tl-bar-duration"
                style={{ left: `${barLeft + barWidth + 0.5}%` }}
              >
                {formatDuration(row.span.duration_ns)}
              </span>
            </div>
          </div>
        )
      })}

      {/* Tooltip */}
      {hoveredSpan && (
        <div
          className="tooltip"
          style={{
            position: 'fixed',
            left: hoveredSpan.x + 12,
            top: hoveredSpan.y - 8,
            zIndex: 500,
            pointerEvents: 'none',
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 2 }}>{hoveredSpan.span.span_name}</div>
          <div className="text-muted" style={{ fontSize: 11 }}>
            {getSpanType(hoveredSpan.span)} · {formatDuration(hoveredSpan.span.duration_ns)}
          </div>
        </div>
      )}
    </div>
  )
}
