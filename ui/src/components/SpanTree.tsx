import { useState, useMemo } from 'react'
import { SpanDetail, formatDuration } from '../api/sessions'
import { SpanNode, getSpanType, typeBadgeClass, durationFillClass, buildTree } from '../lib/spanUtils'

interface SpanTreeProps {
  spans: SpanDetail[]
  traceDurationNs: number
  traceStartNs: number
  selectedSpanId: string | null
  onSpanSelect: (span: SpanDetail) => void
}

function flattenVisible(roots: SpanNode[], collapsed: Set<string>): SpanNode[] {
  const result: SpanNode[] = []
  function dfs(node: SpanNode) {
    result.push(node)
    if (!collapsed.has(node.span_id)) {
      for (const child of node.children) dfs(child)
    }
  }
  roots.forEach(dfs)
  return result
}

export default function SpanTree({ spans, traceDurationNs, traceStartNs, selectedSpanId, onSpanSelect }: SpanTreeProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  const roots = useMemo(() => buildTree(spans), [spans])
  const visible = useMemo(() => flattenVisible(roots, collapsed), [roots, collapsed])

  const toggleCollapse = (spanId: string) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(spanId)) next.delete(spanId)
      else next.add(spanId)
      return next
    })
  }

  return (
    <div className="span-tree">
      <div className="span-tree-header">
        <span className="span-tree-col-name">Span</span>
        <span className="span-tree-col-duration">Duration</span>
      </div>
      {visible.map(node => {
        const type = getSpanType(node)
        const offsetPct = traceDurationNs > 0
          ? ((node.start_ns - traceStartNs) / traceDurationNs) * 100
          : 0
        const widthPct = traceDurationNs > 0
          ? (node.duration_ns / traceDurationNs) * 100
          : 0
        const isError = node.status_code === 'STATUS_CODE_ERROR'
        const hasChildren = node.children.length > 0
        const isCollapsed = collapsed.has(node.span_id)

        return (
          <div
            key={node.span_id}
            className={`span-row${selectedSpanId === node.span_id ? ' selected' : ''}`}
            onClick={() => onSpanSelect(node)}
          >
            {/* Indent + toggle */}
            <span className="span-indent" style={{ width: node.depth * 20 }} />
            {hasChildren ? (
              <button
                className="span-toggle"
                onClick={e => { e.stopPropagation(); toggleCollapse(node.span_id) }}
              >
                {isCollapsed ? '▶' : '▼'}
              </button>
            ) : (
              <span className="span-toggle-placeholder" />
            )}

            {/* Type badge */}
            <span className={typeBadgeClass(type)}>{type}</span>

            {/* Span name */}
            <span className="span-name" title={node.span_name}>{node.span_name}</span>

            {/* Status icon */}
            {isError ? (
              <svg className="span-status-icon" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="7" stroke="#FC0404" strokeWidth="1.5" />
                <path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="#FC0404" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            ) : (
              <svg className="span-status-icon" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="7" stroke="#40706C" strokeWidth="1.5" />
                <path d="M5 8l2 2 4-4" stroke="#40706C" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}

            {/* Duration bar */}
            <div className="duration-track">
              <div
                className={durationFillClass(type)}
                style={{
                  left: `${Math.max(0, Math.min(offsetPct, 100))}%`,
                  width: `${Math.max(0.5, Math.min(widthPct, 100 - offsetPct))}%`,
                }}
              />
            </div>

            {/* Duration label */}
            <span className="span-duration-label">{formatDuration(node.duration_ns)}</span>
          </div>
        )
      })}
    </div>
  )
}
