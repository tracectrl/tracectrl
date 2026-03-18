import { SpanDetail } from '../api/sessions'

export interface SpanNode extends SpanDetail {
  depth: number
  children: SpanNode[]
}

export function getSpanType(span: SpanDetail): string {
  return span.attributes['openinference.span.kind']
    || span.attributes['oi.span_kind']
    || span.span_kind
    || 'INTERNAL'
}

export function typeBadgeClass(type: string): string {
  const t = type.toUpperCase()
  if (t === 'AGENT') return 'badge badge-agent'
  if (t === 'TOOL') return 'badge badge-tool'
  if (t === 'LLM') return 'badge badge-llm'
  if (t === 'CHAIN') return 'badge badge-chain'
  if (t === 'RETRIEVER') return 'badge badge-retriever'
  if (t === 'EMBEDDING') return 'badge badge-embedding'
  return 'badge badge-default'
}

export function durationFillClass(type: string): string {
  const t = type.toUpperCase()
  if (t === 'AGENT') return 'duration-fill duration-fill-agent'
  if (t === 'TOOL') return 'duration-fill duration-fill-tool'
  if (t === 'LLM') return 'duration-fill duration-fill-llm'
  if (t === 'CHAIN') return 'duration-fill duration-fill-chain'
  if (t === 'RETRIEVER') return 'duration-fill duration-fill-retriever'
  return 'duration-fill duration-fill-default'
}

// Color map for inline styles (timeline bars use absolute positioning)
export const SPAN_KIND_COLORS: Record<string, string> = {
  AGENT: '#4A90D9',
  TOOL: '#22C55E',
  LLM: '#FFBB00',
  CHAIN: '#A78BFA',
  RETRIEVER: '#FF6B35',
  EMBEDDING: '#6B6B6B',
  INTERNAL: '#3A3A3A',
  DEFAULT: '#6B6B6B',
}

export function getSpanColor(type: string): string {
  return SPAN_KIND_COLORS[type.toUpperCase()] || SPAN_KIND_COLORS.INTERNAL
}

export function buildTree(spans: SpanDetail[]): SpanNode[] {
  const nodeMap = new Map<string, SpanNode>()
  for (const span of spans) {
    nodeMap.set(span.span_id, { ...span, depth: 0, children: [] })
  }
  const roots: SpanNode[] = []
  for (const node of nodeMap.values()) {
    if (node.parent_span_id && nodeMap.has(node.parent_span_id)) {
      nodeMap.get(node.parent_span_id)!.children.push(node)
    } else {
      roots.push(node)
    }
  }
  function assignDepth(node: SpanNode, depth: number) {
    node.depth = depth
    for (const child of node.children) assignDepth(child, depth + 1)
  }
  roots.forEach(r => assignDepth(r, 0))
  return roots
}
