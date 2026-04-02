import { useState, useMemo } from 'react'
import { SpanDetail, formatDuration } from '../api/sessions'
import { SpanNode, getSpanType, getSpanColor, buildTree } from '../lib/spanUtils'

const SPAN_TYPE_EMOJI: Record<string, string> = {
  AGENT: '🤖',
  TOOL: '🔧',
  LLM: '🧠',
  CHAIN: '🔗',
  RETRIEVER: '📥',
  EMBEDDING: '📊',
  OPENCLAW: '🦞',
  INTERNAL: '⚙️',
}

interface TraceTreeViewProps {
  spans: SpanDetail[]
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

/** Build a map of span_id -> { isLast: boolean, parentId: string | null } for connector lines */
function buildPositionMap(roots: SpanNode[]): Map<string, { isLast: boolean; ancestorIsLast: boolean[] }> {
  const map = new Map<string, { isLast: boolean; ancestorIsLast: boolean[] }>()

  function walk(node: SpanNode, ancestorIsLast: boolean[]) {
    map.set(node.span_id, { isLast: false, ancestorIsLast: [...ancestorIsLast] })
    node.children.forEach((child, idx) => {
      const isLast = idx === node.children.length - 1
      map.set(child.span_id, { isLast, ancestorIsLast: [...ancestorIsLast] })
      walk(child, [...ancestorIsLast, isLast])
    })
  }

  roots.forEach(r => walk(r, []))
  return map
}

export default function TraceTreeView({ spans, selectedSpanId, onSpanSelect }: TraceTreeViewProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set())

  const roots = useMemo(() => buildTree(spans), [spans])
  const visible = useMemo(() => flattenVisible(roots, collapsed), [roots, collapsed])
  const positionMap = useMemo(() => buildPositionMap(roots), [roots])

  const toggleCollapse = (spanId: string) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(spanId)) next.delete(spanId)
      else next.add(spanId)
      return next
    })
  }

  return (
    <div className="trace-tree-view">
      {visible.map(node => {
        const type = getSpanType(node)
        const color = getSpanColor(type)
        const hasChildren = node.children.length > 0
        const isCollapsed = collapsed.has(node.span_id)
        const pos = positionMap.get(node.span_id)

        return (
          <div
            key={node.span_id}
            className={`trace-tree-node${selectedSpanId === node.span_id ? ' selected' : ''}`}
            role="button"
            tabIndex={0}
            onClick={() => onSpanSelect(node)}
            onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSpanSelect(node) } }}
          >
            {/* Indentation connectors */}
            <div className="trace-tree-indent">
              {Array.from({ length: node.depth }, (_, i) => {
                // For each depth level, draw a vertical connector line
                // unless the ancestor at that level was the last child
                const ancestorIsLast = pos?.ancestorIsLast[i] ?? false
                return (
                  <div
                    key={i}
                    className="trace-tree-connector"
                  >
                    {!ancestorIsLast && (
                      <div className="trace-tree-vline" />
                    )}
                  </div>
                )
              })}
              {/* Horizontal connector for non-root nodes */}
              {node.depth > 0 && (
                <div className={`trace-tree-connector trace-tree-hconnector${pos?.isLast ? ' last-child' : ''}`}>
                  <div className="trace-tree-vline-half" style={{ height: pos?.isLast ? '50%' : '100%' }} />
                  <div className="trace-tree-hline" />
                </div>
              )}
            </div>

            {/* Type emoji */}
            <span className="trace-tree-emoji" style={{ color }}>
              {SPAN_TYPE_EMOJI[type.toUpperCase()] || '⚙️'}
            </span>

            {/* Span name */}
            <span className="trace-tree-name" title={node.span_name}>
              {node.span_name}
            </span>

            {/* Duration */}
            <span className="trace-tree-duration">
              {formatDuration(node.duration_ns)}
            </span>

            {/* Collapse chevron */}
            {hasChildren && (
              <button
                className="trace-tree-chevron"
                onClick={e => { e.stopPropagation(); toggleCollapse(node.span_id) }}
                aria-expanded={!isCollapsed}
                aria-label="Toggle children"
              >
                {isCollapsed ? '\u25B6' : '\u25BC'}
              </button>
            )}
          </div>
        )
      })}
    </div>
  )
}
