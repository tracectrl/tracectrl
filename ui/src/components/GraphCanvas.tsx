import { useEffect, useRef } from 'react'
import cytoscape, { Core } from 'cytoscape'
import dagre from 'cytoscape-dagre'
import { TopologyGraph, TopologyNode } from '../api/client'
import { AgentRisk } from '../api/risk'
import { PhaseGroup } from '../hooks/usePhaseInference'

cytoscape.use(dagre)

interface GraphCanvasProps {
  data: TopologyGraph | null
  onNodeSelect: (node: TopologyNode | null) => void
  highlightedNodeIds?: Set<string>
  phaseGroups?: PhaseGroup[]
  showPhases?: boolean
  attackerView?: boolean
  agentRisks?: AgentRisk[]
}

/**
 * Build Cytoscape elements. When showPhases is true, creates compound parent
 * nodes for each phase and adds "then" edges between consecutive phases.
 * This makes dagre treat phases as grouped tiers in a vertical tree.
 */
function buildElements(
  data: TopologyGraph,
  phaseGroups: PhaseGroup[] | undefined,
  showPhases: boolean,
): cytoscape.ElementDefinition[] {
  const elements: cytoscape.ElementDefinition[] = []

  // Build a lookup: agent node ID → phase index (for parenting)
  const agentToPhase = new Map<string, number>()
  if (showPhases && phaseGroups && phaseGroups.length > 0) {
    for (const phase of phaseGroups) {
      for (const agentId of phase.agentIds) {
        agentToPhase.set(agentId, phase.phaseIndex)
      }
    }

    // Add compound parent nodes for each phase
    for (const phase of phaseGroups) {
      elements.push({
        data: {
          id: `__phase_${phase.phaseIndex}`,
          label: `Phase ${phase.phaseIndex + 1}`,
          nodeType: 'phase',
        },
      })
    }

    // Add "then" edges between consecutive phase compound nodes
    for (let i = 0; i < phaseGroups.length - 1; i++) {
      elements.push({
        data: {
          id: `__phase_edge_${i}`,
          source: `__phase_${i}`,
          target: `__phase_${i + 1}`,
          edgeType: 'phase_flow',
          edgeLabel: 'then',
        },
      })
    }
  }

  // Add regular nodes — parent them to phase compounds when active
  for (const n of data.nodes) {
    const parentPhase = agentToPhase.get(n.id)
      ?? agentToPhase.get(n.label.toLowerCase().replace(/\s+/g, '-'))
    const parentId = (showPhases && parentPhase !== undefined)
      ? `__phase_${parentPhase}`
      : undefined

    elements.push({
      data: {
        id: n.id,
        label: n.label,
        nodeType: n.type,
        meta: n.metadata,
        ...(parentId ? { parent: parentId } : {}),
      },
    })
  }

  // Add regular edges
  for (const e of data.edges) {
    elements.push({
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        edgeType: e.type,
        edgeLabel: e.type === 'agent_to_tool'
          ? 'uses'
          : (e.channel === 'team_member' ? 'delegates' : 'calls'),
        callCount: e.call_count,
        channel: e.channel,
      },
    })
  }

  return elements
}

export default function GraphCanvas({
  data, onNodeSelect, highlightedNodeIds, phaseGroups, showPhases, attackerView, agentRisks,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const onNodeSelectRef = useRef(onNodeSelect)
  onNodeSelectRef.current = onNodeSelect

  // Rebuild the graph when data OR showPhases changes
  // (showPhases changes the element structure — compound nodes)
  useEffect(() => {
    if (!containerRef.current || !data || data.nodes.length === 0) return

    if (cyRef.current) {
      cyRef.current.destroy()
      cyRef.current = null
    }

    const elements = buildElements(data, phaseGroups, !!showPhases)

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        // Phase compound nodes — subtle container
        {
          selector: 'node[nodeType="phase"]',
          style: {
            'background-color': 'rgba(64, 112, 108, 0.08)',
            'background-opacity': 1,
            'border-width': 1.5,
            'border-color': 'rgba(64, 112, 108, 0.4)',
            'border-style': 'solid',
            'shape': 'round-rectangle',
            'padding': '24px',
            'label': 'data(label)',
            'color': '#8BC4BF',
            'font-size': '11px',
            'font-weight': 700,
            'font-family': "'JetBrains Mono', monospace",
            'text-valign': 'top',
            'text-halign': 'center',
            'text-margin-y': -4,
          },
        },
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
        // Phase flow edges — bright, visible "then" arrows
        {
          selector: 'edge[edgeType="phase_flow"]',
          style: {
            'line-color': '#8BC4BF',
            'target-arrow-color': '#8BC4BF',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'line-style': 'dashed',
            'line-dash-pattern': [8, 5],
            'width': 2.5,
            'opacity': 0.9,
            'label': 'data(edgeLabel)',
            'font-size': '11px',
            'font-weight': 600,
            'font-family': "'JetBrains Mono', monospace",
            'color': '#8BC4BF',
            'text-rotation': 'autorotate',
            'text-margin-y': -12,
            'text-background-color': '#0A0A0A',
            'text-background-opacity': 0.85,
            'text-background-padding': '4px',
            'text-background-shape': 'roundrectangle' as any,
          },
        },
        // Agent-to-agent edges — solid, visible
        {
          selector: 'edge[edgeType="agent_to_agent"]',
          style: {
            'line-color': '#AAAAAA',
            'target-arrow-color': '#AAAAAA',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'width': 2,
            'opacity': 0.8,
            'label': 'data(edgeLabel)',
            'font-size': '10px',
            'font-family': "'Poppins', sans-serif",
            'color': '#AAAAAA',
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
            'text-background-color': '#0A0A0A',
            'text-background-opacity': 0.8,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle' as any,
          },
        },
        // Agent-to-tool edges — dashed, white arrows
        {
          selector: 'edge[edgeType="agent_to_tool"]',
          style: {
            'line-color': '#CCCCCC',
            'target-arrow-color': '#CCCCCC',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'line-style': 'dashed',
            'line-dash-pattern': [6, 4],
            'width': 1.5,
            'opacity': 0.7,
            'label': 'data(edgeLabel)',
            'font-size': '10px',
            'font-family': "'Poppins', sans-serif",
            'color': '#CCCCCC',
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
            'text-background-color': '#0A0A0A',
            'text-background-opacity': 0.8,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle' as any,
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
        nodeSep: 50,
        rankSep: showPhases ? 60 : 80,
        animate: false,
        fit: true,
        padding: 40,
      } as any,
      minZoom: 0.3,
      maxZoom: 3,
    })

    const currentData = data
    cyRef.current.on('tap', 'node', (evt) => {
      const nodeData = evt.target.data()
      if (nodeData.nodeType === 'phase') return // Don't select phase containers
      const node = currentData.nodes.find(n => n.id === nodeData.id)
      onNodeSelectRef.current(node || null)
    })

    cyRef.current.on('tap', (evt) => {
      if (evt.target === cyRef.current) {
        onNodeSelectRef.current(null)
      }
    })

    return () => {
      cyRef.current?.destroy()
      cyRef.current = null
    }
  }, [data, showPhases, phaseGroups])

  // Highlight effect
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    cy.startBatch()
    if (highlightedNodeIds && highlightedNodeIds.size > 0) {
      cy.nodes().forEach((node) => {
        const nodeId = node.data('id') as string
        const nodeLabel = node.data('label') as string
        const nodeType = node.data('nodeType') as string
        if (nodeType === 'phase') return
        const isHighlighted =
          highlightedNodeIds.has(nodeId) ||
          highlightedNodeIds.has(nodeLabel?.toLowerCase().replace(/\s+/g, '-'))
        node.style('opacity', isHighlighted ? 1.0 : 0.2)
      })
      cy.edges().forEach((edge) => {
        const edgeType = edge.data('edgeType') as string
        if (edgeType === 'phase_flow') return
        edge.style('opacity', 0.15)
      })
    } else {
      cy.nodes().forEach((node) => { node.style('opacity', 1.0) })
      cy.edges().forEach((edge) => { edge.removeStyle('opacity') })
    }
    cy.endBatch()
  }, [highlightedNodeIds])

  // Attacker view effect
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    cy.startBatch()
    if (attackerView && agentRisks && agentRisks.length > 0) {
      const riskMap = new Map<string, string>()
      for (const r of agentRisks) riskMap.set(r.agent_id, r.severity)

      const colorMap: Record<string, string> = {
        critical: '#FF4D4D', high: '#FF6B35', medium: '#FFBB00', low: '#22C55E',
      }

      cy.nodes().forEach((node) => {
        const nodeId = node.data('id') as string
        const nodeLabel = node.data('label') as string
        const severity = riskMap.get(nodeId) || riskMap.get(nodeLabel?.toLowerCase().replace(/\s+/g, '-'))
        if (severity) {
          node.style('border-color', colorMap[severity.toLowerCase()] || '#22C55E')
          node.style('border-width', 3)
        }
      })
    } else {
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

  return (
    <div className="graph-canvas-wrapper" role="img" aria-label={`Agent topology graph with ${data?.nodes.length ?? 0} nodes and ${data?.edges.length ?? 0} edges`}>
      <div className="sr-only">
        Topology graph: {data?.nodes.filter(n => n.type === 'agent').length ?? 0} agents,{' '}
        {data?.nodes.filter(n => n.type === 'tool').length ?? 0} tools,{' '}
        {data?.edges.length ?? 0} connections.{' '}
        {data?.nodes.filter(n => n.type === 'agent').map(n => n.label).join(', ')}
      </div>
      <div ref={containerRef} className="graph-canvas" />
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
              <span className="graph-legend-dot" style={{ background: 'rgba(64, 112, 108, 0.4)', border: '1px solid #8BC4BF' }} />
              Phase
            </div>
            <div className="graph-legend-item">
              <span className="graph-legend-line" style={{ background: 'repeating-linear-gradient(to right, #8BC4BF 0px, #8BC4BF 5px, transparent 5px, transparent 8px)' }} />
              then
            </div>
          </>
        )}
      </div>
    </div>
  )
}
