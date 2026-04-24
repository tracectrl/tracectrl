import { useEffect, useRef, useState } from 'react'
import cytoscape, { Core } from 'cytoscape'
import dagre from 'cytoscape-dagre'
import { TopologyGraph, TopologyNode, AttackOverlay, AttackPath } from '../api/client'
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
  attackMode?: boolean
  overlay?: AttackOverlay | null
  selectedAttackPath?: AttackPath | null
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

  // Add regular edges (always include all edges, we control visibility with styles)
  for (const e of data.edges) {
    let edgeLabel = ''
    if (e.type === 'agent_to_tool') {
      edgeLabel = 'uses'
    } else if (e.type === 'agent_return') {
      edgeLabel = 'returns'
    } else if (e.type === 'tool_return') {
      edgeLabel = 'returns'
    } else if (e.type === 'ingress_to_agent') {
      edgeLabel = 'triggers'
    } else {
      edgeLabel = e.channel === 'team_member' ? 'delegates' : 'calls'
    }

    elements.push({
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        edgeType: e.type,
        edgeLabel,
        callCount: e.call_count,
        channel: e.channel,
      },
    })
  }

  return elements
}

export default function GraphCanvas({
  data, onNodeSelect, highlightedNodeIds, phaseGroups, showPhases, attackerView, agentRisks, attackMode, overlay, selectedAttackPath
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const onNodeSelectRef = useRef(onNodeSelect)
  onNodeSelectRef.current = onNodeSelect

  // State for toggling return edges (show them in attack mode, hide by default otherwise)
  const [showReturnEdges, setShowReturnEdges] = useState(false)

  // Auto-show return edges in attack mode
  useEffect(() => {
    if (attackMode) {
      setShowReturnEdges(true)
    }
  }, [attackMode])

  // Rebuild the graph when data OR showPhases changes
  // (showPhases changes the element structure — compound nodes)
  // Always include return edges but control visibility with styles
  useEffect(() => {
    if (!containerRef.current || !data || data.nodes.length === 0) return

    if (cyRef.current) {
      cyRef.current.destroy()
      cyRef.current = null
    }

    // Build topology elements
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
        // Agent nodes — neon blue hexagons
        {
          selector: 'node[nodeType="agent"]',
          style: {
            'background-color': '#010D1C',
            'label': 'data(label)',
            'color': '#A8C0D6',
            'font-size': '12px',
            'font-weight': 600,
            'font-family': "'Poppins', sans-serif",
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': '120px',
            'text-margin-y': 9,
            'text-background-color': '#050810',
            'text-background-opacity': 0.9,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'width': 'label',
            'height': 50,
            'padding': '16px',
            'shape': 'hexagon',
            'border-width': 2.5,
            'border-color': '#4D9EFF',
            'border-opacity': 0.95,
          },
        },
        // Tool nodes — neon green cutrectangles
        {
          selector: 'node[nodeType="tool"]',
          style: {
            'background-color': '#001A0A',
            'label': 'data(label)',
            'color': '#A8C0D6',
            'font-size': '11px',
            'font-weight': 500,
            'font-family': "'JetBrains Mono', monospace",
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': '100px',
            'text-margin-y': 9,
            'text-background-color': '#050810',
            'text-background-opacity': 0.9,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'width': 'label',
            'height': 40,
            'padding': '14px',
            'shape': 'cut-rectangle',
            'border-width': 2,
            'border-color': '#00E676',
            'border-opacity': 0.95,
          },
        },
        // Ingress nodes — neon cyan diamonds
        {
          selector: 'node[nodeType="ingress"]',
          style: {
            'background-color': '#001A22',
            'label': 'data(label)',
            'color': '#A8C0D6',
            'font-size': '11px',
            'font-weight': 600,
            'font-family': "'JetBrains Mono', monospace",
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': '100px',
            'text-margin-y': 9,
            'text-background-color': '#050810',
            'text-background-opacity': 0.9,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
            'width': 'label',
            'height': 40,
            'padding': '14px',
            'shape': 'diamond',
            'border-width': 3,
            'border-color': '#00D4FF',
            'border-opacity': 0.95,
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
        // Agent-to-agent edges — solid, visible (delegation)
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
        // Agent return edges — dashed, lighter (data flow back)
        {
          selector: 'edge[edgeType="agent_return"]',
          style: {
            'line-color': '#888888',
            'target-arrow-color': '#888888',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'line-style': 'dashed',
            'line-dash-pattern': [5, 5],
            'width': 1.5,
            'opacity': 0.5,
            'display': 'none',  // Hidden by default, shown when showReturnEdges=true
            'label': 'data(edgeLabel)',
            'font-size': '9px',
            'font-family': "'Poppins', sans-serif",
            'color': '#888888',
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
            'text-background-color': '#0A0A0A',
            'text-background-opacity': 0.7,
            'text-background-padding': '2px',
            'text-background-shape': 'roundrectangle' as any,
          },
        },
        // Tool return edges — dashed, lighter (data flow back from tools)
        {
          selector: 'edge[edgeType="tool_return"]',
          style: {
            'line-color': '#999999',
            'target-arrow-color': '#999999',
            'target-arrow-shape': 'triangle',
            'curve-style': 'unbundled-bezier',
            'control-point-distances': 30,
            'control-point-weights': 0.5,
            'line-style': 'dashed',
            'line-dash-pattern': [5, 5],
            'width': 1.5,
            'opacity': 0.5,
            'display': 'none',  // Hidden by default, shown when showReturnEdges=true
            'label': 'data(edgeLabel)',
            'font-size': '9px',
            'font-family': "'Poppins', sans-serif",
            'color': '#999999',
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
            'text-background-color': '#0A0A0A',
            'text-background-opacity': 0.7,
            'text-background-padding': '2px',
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
            'curve-style': 'straight',
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
        // Ingress-to-agent edges — bold orange arrows indicating entry points
        {
          selector: 'edge[edgeType="ingress_to_agent"]',
          style: {
            'line-color': '#F97316',
            'target-arrow-color': '#F97316',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'width': 2.5,
            'opacity': 0.9,
            'label': 'data(edgeLabel)',
            'font-size': '10px',
            'font-weight': 600,
            'font-family': "'JetBrains Mono', monospace",
            'color': '#F97316',
            'text-rotation': 'autorotate',
            'text-margin-y': -10,
            'text-background-color': '#0A0A0A',
            'text-background-opacity': 0.85,
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
        nodeSep: 100,
        rankSep: 70,
        animate: false,
        fit: true,
        padding: 80,
        ranker: 'tight-tree',
        edgeSep: 20,
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

    // Drag agent nodes to move their tools along
    cyRef.current.on('grab', 'node[nodeType="agent"]', (evt) => {
      const agent = evt.target
      // Store agent's starting position
      agent.data('dragStartPos', { x: agent.position().x, y: agent.position().y })

      // Store all connected tools' starting positions (only once!)
      agent.connectedEdges('[edgeType="agent_to_tool"]').targets('[nodeType="tool"]').forEach((tool: any) => {
        tool.data('toolStartPos', { x: tool.position().x, y: tool.position().y })
      })
    })

    cyRef.current.on('drag', 'node[nodeType="agent"]', (evt) => {
      const agent = evt.target
      const startPos = agent.data('dragStartPos')
      if (!startPos) return

      // Calculate how far agent has moved from start
      const deltaX = agent.position().x - startPos.x
      const deltaY = agent.position().y - startPos.y

      // Move tools by same delta from THEIR stored start positions
      agent.connectedEdges('[edgeType="agent_to_tool"]').targets('[nodeType="tool"]').forEach((tool: any) => {
        const toolStartPos = tool.data('toolStartPos')
        if (toolStartPos) {
          tool.position({
            x: toolStartPos.x + deltaX,
            y: toolStartPos.y + deltaY
          })
        }
      })
    })

    cyRef.current.on('free', 'node[nodeType="agent"]', (evt) => {
      const agent = evt.target
      agent.removeData('dragStartPos')
      // Clean up tool start positions
      agent.connectedEdges('[edgeType="agent_to_tool"]').targets('[nodeType="tool"]').forEach((tool: any) => {
        tool.removeData('toolStartPos')
      })
    })

    return () => {
      cyRef.current?.destroy()
      cyRef.current = null
    }
  }, [data, showPhases, phaseGroups])  // Removed showReturnEdges and attackMode - we handle them separately

  // Toggle return edge visibility without rebuilding graph
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    const returnEdges = cy.edges('[edgeType="agent_return"], [edgeType="tool_return"]')
    if (showReturnEdges || attackMode) {
      returnEdges.style('display', 'element')  // Show return edges
    } else {
      returnEdges.style('display', 'none')  // Hide return edges
    }
  }, [showReturnEdges, attackMode])

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
          node.style('border-color', '#4D9EFF')
          node.style('border-width', 2.5)
        } else if (nodeType === 'tool') {
          node.style('border-color', '#00E676')
          node.style('border-width', 2)
        } else if (nodeType === 'ingress') {
          node.style('border-color', '#00D4FF')
          node.style('border-width', 3)
        }
      })
    }
    cy.endBatch()
  }, [attackerView, agentRisks])

  // Attack mode styling effect
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return

    if (attackMode && overlay) {
      cy.startBatch()

      if (selectedAttackPath) {
        // DETAIL MODE: Specific path selected - highlight only that path

        // Reset all node styles (clear overview mode highlighting)
        cy.nodes().removeStyle('border-color border-width')

        // Dim all edges
        cy.edges().style({ opacity: 0.15 })

        // Build set of nodes and edges in the selected path
        const pathNodes = new Set(selectedAttackPath.path_nodes)
        const pathEdges = new Set(selectedAttackPath.path_edges)

        // Highlight nodes in the path
        pathNodes.forEach(nodeId => {
          const node = cy.$(`#${nodeId}`)
          if (node.length > 0 && node.data('nodeType') === 'agent') {
            node.style({
              'border-color': '#EF4444',
              'border-width': 4,
            })
          }
        })

        // Highlight edges in the path by matching edge IDs
        pathEdges.forEach(edgeId => {
          const edge = cy.$(`#${edgeId}`)
          if (edge.length > 0) {
            edge.style({
              'line-color': '#EF4444',
              'target-arrow-color': '#EF4444',
              'width': 3,
              'opacity': 1,
            })
          }
        })

      } else {
        // OVERVIEW MODE: No specific path selected - show at-risk overview

        // Don't dim edges in overview mode - keep normal opacity
        cy.edges().removeStyle('opacity')

        // Add red borders to at-risk agents
        overlay.compromised_nodes.forEach(({ node_id }) => {
          const node = cy.$(`#${node_id}`)
          if (node.length > 0 && node.data('nodeType') === 'agent') {
            node.style({
              'border-color': '#EF4444',
              'border-width': 3,
            })
          }
        })

        // Add alert icons to risky ingress points
        // Check which ingress nodes have attack edges
        const riskyIngressNodes = new Set<string>()
        overlay.attack_edges.forEach(({ source }) => {
          if (source.startsWith('ingress:')) {
            riskyIngressNodes.add(source)
          }
        })

        riskyIngressNodes.forEach(nodeId => {
          const node = cy.$(`#${nodeId}`)
          if (node.length > 0) {
            node.style({
              'border-color': '#EF4444',
              'border-width': 4,
            })
          }
        })
      }

      cy.endBatch()
    } else {
      // Restore original styles when attack mode is off
      cy.elements().removeStyle()
    }
  }, [attackMode, overlay, selectedAttackPath])

  return (
    <div className="graph-canvas-wrapper" role="img" aria-label={`Agent topology graph with ${data?.nodes.length ?? 0} nodes and ${data?.edges.length ?? 0} edges`}>
      <div className="sr-only">
        Topology graph: {data?.nodes.filter(n => n.type === 'agent').length ?? 0} agents,{' '}
        {data?.nodes.filter(n => n.type === 'tool').length ?? 0} tools,{' '}
        {data?.edges.length ?? 0} connections.{' '}
        {data?.nodes.filter(n => n.type === 'agent').map(n => n.label).join(', ')}
      </div>
      <div ref={containerRef} className="graph-canvas" />

      {!attackMode && (
        <button
          type="button"
          onClick={() => setShowReturnEdges(!showReturnEdges)}
          className={`graph-canvas-toolbtn${showReturnEdges ? ' is-active' : ''}`}
          aria-pressed={showReturnEdges}
        >
          {showReturnEdges ? '✓ ' : ''}Show Data Flow
        </button>
      )}

      <div className="graph-legend">
        <div className="graph-legend-item">
          <span className="graph-legend-dot graph-legend-dot--agent" />
          Agent
        </div>
        <div className="graph-legend-item">
          <span className="graph-legend-dot graph-legend-dot--tool" />
          Tool
        </div>
        <div className="graph-legend-item">
          <span className="graph-legend-dot graph-legend-dot--trigger" />
          Trigger
        </div>
        <div className="graph-legend-divider" />
        <div className="graph-legend-item">
          <span className="graph-legend-line graph-legend-line-solid" />
          delegates
        </div>
        <div className="graph-legend-item">
          <span className="graph-legend-line graph-legend-line-dashed" style={{ opacity: 0.5 }} />
          returns
        </div>
        <div className="graph-legend-item">
          <span className="graph-legend-line graph-legend-line-dashed" />
          uses
        </div>
        {showPhases && (
          <>
            <div className="graph-legend-divider" />
            <div className="graph-legend-item">
              <span className="graph-legend-dot graph-legend-dot--phase" />
              Phase
            </div>
            <div className="graph-legend-item">
              <span className="graph-legend-line graph-legend-line--then" />
              then
            </div>
          </>
        )}
      </div>
    </div>
  )
}
