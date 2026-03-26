import { useEffect, useRef, useState, useCallback } from 'react'
import cytoscape, { Core } from 'cytoscape'
import dagre from 'cytoscape-dagre'
import { TopologyGraph, TopologyNode } from '../api/client'
import { AgentRisk } from '../api/risk'
import { PhaseGroup } from '../hooks/usePhaseInference'

cytoscape.use(dagre)

interface PhaseBox {
  phaseIndex: number
  x: number
  y: number
  w: number
  h: number
}

interface GraphCanvasProps {
  data: TopologyGraph | null
  onNodeSelect: (node: TopologyNode | null) => void
  highlightedNodeIds?: Set<string>
  phaseGroups?: PhaseGroup[]
  showPhases?: boolean
  attackerView?: boolean
  agentRisks?: AgentRisk[]
}

export default function GraphCanvas({ data, onNodeSelect, highlightedNodeIds, phaseGroups, showPhases, attackerView, agentRisks }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const onNodeSelectRef = useRef(onNodeSelect)
  onNodeSelectRef.current = onNodeSelect

  const [phaseBoxes, setPhaseBoxes] = useState<PhaseBox[]>([])

  const recalcPhaseBoxes = useCallback(() => {
    const cy = cyRef.current
    if (!cy || !phaseGroups || !showPhases) {
      setPhaseBoxes([])
      return
    }

    const boxes: PhaseBox[] = []
    for (const phase of phaseGroups) {
      const matchingNodes: cytoscape.NodeSingular[] = []
      cy.nodes().forEach((node) => {
        const nodeId = node.data('id') as string
        const nodeLabel = node.data('label') as string
        if (
          phase.agentIds.includes(nodeId) ||
          phase.agentIds.includes(nodeLabel?.toLowerCase().replace(/\s+/g, '-'))
        ) {
          matchingNodes.push(node)
        }
      })

      if (matchingNodes.length === 0) continue

      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      for (const node of matchingNodes) {
        const bb = node.renderedBoundingBox()
        if (bb.x1 < minX) minX = bb.x1
        if (bb.y1 < minY) minY = bb.y1
        if (bb.x2 > maxX) maxX = bb.x2
        if (bb.y2 > maxY) maxY = bb.y2
      }

      const pad = 20
      boxes.push({
        phaseIndex: phase.phaseIndex,
        x: minX - pad,
        y: minY - pad,
        w: maxX - minX + pad * 2,
        h: maxY - minY + pad * 2,
      })
    }
    setPhaseBoxes(boxes)
  }, [phaseGroups, showPhases])

  const recalcRef = useRef(recalcPhaseBoxes)
  recalcRef.current = recalcPhaseBoxes

  // Layout effect — only re-runs when graph data changes
  useEffect(() => {
    if (!containerRef.current || !data || data.nodes.length === 0) return

    if (cyRef.current) {
      cyRef.current.destroy()
      cyRef.current = null
    }

    const elements: cytoscape.ElementDefinition[] = [
      ...data.nodes.map(n => ({
        data: { id: n.id, label: n.label, nodeType: n.type, meta: n.metadata },
      })),
      ...data.edges.map(e => ({
        data: {
          id: e.id,
          source: e.source,
          target: e.target,
          edgeType: e.type,
          edgeLabel: e.type === 'agent_to_tool' ? 'uses' : (e.channel === 'team_member' ? 'delegates' : 'calls'),
          callCount: e.call_count,
          channel: e.channel,
        },
      })),
    ]

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        // Agent nodes — blue rounded rectangles
        {
          selector: 'node[nodeType="agent"]',
          style: {
            'background-color': '#4A90D9',
            'label': 'data(label)',
            'color': '#F5F5F5',
            'font-size': '12px',
            'font-weight': 600,
            'font-family': "'Poppins', sans-serif",
            'text-valign': 'center',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': '120px',
            'width': 'label',
            'height': 50,
            'padding': '16px',
            'shape': 'round-rectangle',
            'border-width': 2,
            'border-color': 'rgba(74, 144, 217, 0.3)',
          },
        },
        // Tool nodes — green rounded rectangles
        {
          selector: 'node[nodeType="tool"]',
          style: {
            'background-color': '#22C55E',
            'label': 'data(label)',
            'color': '#F5F5F5',
            'font-size': '11px',
            'font-weight': 500,
            'font-family': "'JetBrains Mono', monospace",
            'text-valign': 'center',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': '100px',
            'width': 'label',
            'height': 40,
            'padding': '14px',
            'shape': 'round-rectangle',
            'border-width': 1,
            'border-color': 'rgba(34, 197, 94, 0.3)',
          },
        },
        // Agent-to-agent edges — solid line
        {
          selector: 'edge[edgeType="agent_to_agent"]',
          style: {
            'line-color': '#8A8A8A',
            'target-arrow-color': '#8A8A8A',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'width': 2,
            'opacity': 0.7,
            'label': 'data(edgeLabel)',
            'font-size': '10px',
            'font-family': "'Poppins', sans-serif",
            'color': '#6B6B6B',
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
          },
        },
        // Agent-to-tool edges — dashed line
        {
          selector: 'edge[edgeType="agent_to_tool"]',
          style: {
            'line-color': '#3A3A3A',
            'target-arrow-color': '#3A3A3A',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'line-style': 'dashed',
            'line-dash-pattern': [6, 4],
            'width': 1.5,
            'opacity': 0.5,
            'label': 'data(edgeLabel)',
            'font-size': '10px',
            'font-family': "'Poppins', sans-serif",
            'color': '#6B6B6B',
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
          },
        },
        // Selected state — red glow
        {
          selector: ':selected',
          style: {
            'border-color': '#FC0404',
            'border-width': 3,
            'border-opacity': 1,
          },
        },
      ],
      layout: {
        name: 'dagre',
        rankDir: 'TB',
        nodeSep: 60,
        rankSep: 80,
        animate: false,
        fit: true,
        padding: 50,
      } as any,
      minZoom: 0.3,
      maxZoom: 3,
    })

    // Bind event listeners using ref for stable callback
    const currentData = data
    cyRef.current.on('tap', 'node', (evt) => {
      const nodeData = evt.target.data()
      const node = currentData.nodes.find(n => n.id === nodeData.id)
      onNodeSelectRef.current(node || null)
    })

    cyRef.current.on('tap', (evt) => {
      if (evt.target === cyRef.current) {
        onNodeSelectRef.current(null)
      }
    })

    // Subscribe to render event to recalculate phase boxes on pan/zoom
    cyRef.current.on('render', () => {
      recalcRef.current()
    })

    return () => {
      cyRef.current?.destroy()
      cyRef.current = null
    }
  }, [data])

  // Highlight effect — reacts to highlightedNodeIds changes
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    cy.startBatch()
    if (highlightedNodeIds && highlightedNodeIds.size > 0) {
      cy.nodes().forEach((node) => {
        const nodeId = node.data('id') as string
        const nodeLabel = node.data('label') as string
        const isHighlighted =
          highlightedNodeIds.has(nodeId) ||
          highlightedNodeIds.has(nodeLabel?.toLowerCase().replace(/\s+/g, '-'))
        node.style('opacity', isHighlighted ? 1.0 : 0.2)
      })
      cy.edges().forEach((edge) => {
        edge.style('opacity', 0.2)
      })
    } else {
      cy.nodes().forEach((node) => {
        node.style('opacity', 1.0)
      })
      cy.edges().forEach((edge) => {
        edge.removeStyle('opacity')
      })
    }
    cy.endBatch()
  }, [highlightedNodeIds])

  // Attacker view effect — highlights nodes by risk severity
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    cy.startBatch()
    if (attackerView && agentRisks && agentRisks.length > 0) {
      const riskMap = new Map<string, string>()
      for (const r of agentRisks) {
        riskMap.set(r.agent_id, r.severity)
      }

      const colorMap: Record<string, string> = {
        critical: '#FF4D4D',
        high: '#FF6B35',
        medium: '#FFBB00',
        low: '#22C55E',
      }

      cy.nodes().forEach((node) => {
        const nodeId = node.data('id') as string
        const nodeLabel = node.data('label') as string
        const severity =
          riskMap.get(nodeId) ||
          riskMap.get(nodeLabel?.toLowerCase().replace(/\s+/g, '-'))
        if (severity) {
          const color = colorMap[severity.toLowerCase()] || '#22C55E'
          node.style('border-color', color)
          node.style('border-width', 3)
        }
      })
    } else {
      // Reset to default border styles
      cy.nodes().forEach((node) => {
        const nodeType = node.data('nodeType') as string
        if (nodeType === 'agent') {
          node.style('border-color', 'rgba(74, 144, 217, 0.3)')
          node.style('border-width', 2)
        } else if (nodeType === 'tool') {
          node.style('border-color', 'rgba(34, 197, 94, 0.3)')
          node.style('border-width', 1)
        }
      })
    }
    cy.endBatch()
  }, [attackerView, agentRisks])

  // Recalculate phase boxes when showPhases or phaseGroups change
  useEffect(() => {
    recalcPhaseBoxes()
  }, [recalcPhaseBoxes])

  return (
    <div className="graph-canvas-wrapper" role="img" aria-label={`Agent topology graph with ${data?.nodes.length ?? 0} nodes and ${data?.edges.length ?? 0} edges`}>
      <div className="sr-only">
        Topology graph: {data?.nodes.filter(n => n.type === 'agent').length ?? 0} agents,{' '}
        {data?.nodes.filter(n => n.type === 'tool').length ?? 0} tools,{' '}
        {data?.edges.length ?? 0} connections.{' '}
        {data?.nodes.filter(n => n.type === 'agent').map(n => n.label).join(', ')}
      </div>
      <div ref={containerRef} className="graph-canvas" />
      {/* Phase group boxes */}
      {showPhases && phaseBoxes.map((box) => (
        <div
          key={`phase-${box.phaseIndex}`}
          className="phase-overlay-box"
          style={{
            left: box.x,
            top: box.y,
            width: box.w,
            height: box.h,
          }}
        >
          <div className="phase-overlay-label">Phase {box.phaseIndex + 1}</div>
        </div>
      ))}
      {/* "then" arrows between consecutive phase boxes */}
      {showPhases && phaseBoxes.length > 1 && (
        <svg style={{
          position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
          pointerEvents: 'none', zIndex: 6,
        }}>
          <defs>
            <marker id="phase-arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
              <path d="M0,0 L8,3 L0,6" fill="none" stroke="#40706C" strokeWidth="1.5" />
            </marker>
          </defs>
          {phaseBoxes.slice(0, -1).map((box, i) => {
            const next = phaseBoxes[i + 1]
            const x1 = box.x + box.w / 2
            const y1 = box.y + box.h
            const x2 = next.x + next.w / 2
            const y2 = next.y
            const mx = (x1 + x2) / 2
            const my = (y1 + y2) / 2
            return (
              <g key={`arrow-${i}`}>
                <line
                  x1={x1} y1={y1 + 4} x2={x2} y2={y2 - 4}
                  stroke="#40706C" strokeWidth="1.5" strokeDasharray="6,4"
                  markerEnd="url(#phase-arrow)" opacity="0.7"
                />
                <rect x={mx - 16} y={my - 8} width="32" height="16" rx="4"
                  fill="#0A0A0A" stroke="#40706C" strokeWidth="0.5" opacity="0.9"
                />
                <text x={mx} y={my + 4} textAnchor="middle" fontSize="9"
                  fontFamily="'JetBrains Mono', monospace" fill="#40706C" opacity="0.8"
                >
                  then
                </text>
              </g>
            )
          })}
        </svg>
      )}
      <div className="graph-legend">
        <div className="graph-legend-item">
          <span className="graph-legend-dot" style={{ background: '#4A90D9' }} />
          Agent
        </div>
        <div className="graph-legend-item">
          <span className="graph-legend-dot" style={{ background: '#22C55E' }} />
          Tool
        </div>
        <div className="graph-legend-divider" />
        <div className="graph-legend-item">
          <span className="graph-legend-line graph-legend-line-solid" />
          delegates
        </div>
        <div className="graph-legend-item">
          <span className="graph-legend-line graph-legend-line-dashed" />
          uses
        </div>
        {showPhases && (
          <>
            <div className="graph-legend-divider" />
            <div className="graph-legend-item">
              <span className="graph-legend-line graph-legend-line-dashed" style={{ background: 'repeating-linear-gradient(to right, #40706C 0px, #40706C 4px, transparent 4px, transparent 7px)' }} />
              then
            </div>
          </>
        )}
      </div>
    </div>
  )
}
