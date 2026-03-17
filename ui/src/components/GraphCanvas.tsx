import { useEffect, useRef } from 'react'
import cytoscape, { Core } from 'cytoscape'
import dagre from 'cytoscape-dagre'
import { TopologyGraph, TopologyNode } from '../api/client'

cytoscape.use(dagre)

interface GraphCanvasProps {
  data: TopologyGraph | null
  onNodeSelect: (node: TopologyNode | null) => void
}

export default function GraphCanvas({ data, onNodeSelect }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)
  const onNodeSelectRef = useRef(onNodeSelect)
  onNodeSelectRef.current = onNodeSelect

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

    return () => {
      cyRef.current?.destroy()
      cyRef.current = null
    }
  }, [data])

  return (
    <div className="graph-canvas-wrapper">
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
      </div>
    </div>
  )
}
