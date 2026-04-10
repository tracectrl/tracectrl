import { useEffect, useRef } from 'react'
import cytoscape, { Core } from 'cytoscape'
import dagre from 'cytoscape-dagre'
import { ScanTopology } from '../api/scan'

cytoscape.use(dagre)

const NODE_COLORS: Record<string, string> = {
  INGRESS: '#8BC4BF',
  AGENT: '#4A90D9',
  TOOL: '#22C55E',
  LLM_PROVIDER: '#A78BFA',
  SCHEDULER: '#FFBB00',
  EXTENSION: '#FB923C',
  SUBAGENT_SURFACE: '#F472B6',
  STORAGE: '#6B7280',
  EXTERNAL_SERVICE: '#6B7280',
}

const RISK_BORDER: Record<string, { color: string; width: number }> = {
  critical: { color: '#FF4D4D', width: 4 },
  high: { color: '#FF6B35', width: 3 },
  medium: { color: '#FFBB00', width: 3 },
}

interface ScanTopologyCanvasProps {
  topology: ScanTopology
  nodeRiskMap: Map<string, string>
}

export default function ScanTopologyCanvas({ topology, nodeRiskMap }: ScanTopologyCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)

  // Build and layout graph
  useEffect(() => {
    if (!containerRef.current || topology.nodes.length === 0) return

    if (cyRef.current) {
      cyRef.current.destroy()
      cyRef.current = null
    }

    const elements: cytoscape.ElementDefinition[] = []

    for (const node of topology.nodes) {
      elements.push({
        data: {
          id: node.id,
          label: node.label,
          nodeType: node.type,
        },
      })
    }

    for (const edge of topology.edges) {
      elements.push({
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          edgeType: edge.type,
          label: edge.type.replace(/_/g, ' '),
        },
      })
    }

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#4A90D9',
            'label': 'data(label)',
            'color': '#E0E0E0',
            'font-size': '11px',
            'font-family': "'JetBrains Mono', monospace",
            'text-valign': 'bottom',
            'text-margin-y': 8,
            'width': 36,
            'height': 36,
            'border-width': 1,
            'border-color': 'rgba(255,255,255,0.15)',
            'text-background-color': 'rgba(20,20,20,0.85)',
            'text-background-opacity': 1,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
          },
        },
        // Node type colors
        ...Object.entries(NODE_COLORS).map(([type, color]) => ({
          selector: `node[nodeType="${type}"]`,
          style: { 'background-color': color } as cytoscape.Css.Node,
        })),
        {
          selector: 'edge',
          style: {
            'width': 1.5,
            'line-color': '#555',
            'target-arrow-color': '#555',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.8,
            'label': 'data(label)',
            'font-size': '9px',
            'color': '#999',
            'text-background-color': 'rgba(20,20,20,0.85)',
            'text-background-opacity': 1,
            'text-background-padding': '2px',
            'text-background-shape': 'roundrectangle',
            'text-rotation': 'autorotate',
          } as cytoscape.Css.Edge,
        },
      ],
      layout: {
        name: 'dagre',
        rankDir: 'LR',
        nodeSep: 40,
        rankSep: 70,
        animate: false,
      } as any,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
    })

    return () => {
      cyRef.current?.destroy()
      cyRef.current = null
    }
  }, [topology])

  // Apply risk coloring
  useEffect(() => {
    const cy = cyRef.current
    if (!cy || nodeRiskMap.size === 0) return

    cy.startBatch()
    for (const [nodeId, severity] of nodeRiskMap) {
      const node = cy.getElementById(nodeId)
      if (node.length === 0) continue
      const risk = RISK_BORDER[severity]
      if (risk) {
        node.style({
          'border-width': risk.width,
          'border-color': risk.color,
        })
      }
    }
    cy.endBatch()
  }, [nodeRiskMap, topology])

  const legend = [
    { label: 'Ingress', color: NODE_COLORS.INGRESS },
    { label: 'Agent', color: NODE_COLORS.AGENT },
    { label: 'Tool', color: NODE_COLORS.TOOL },
    { label: 'LLM', color: NODE_COLORS.LLM_PROVIDER },
    { label: 'Extension', color: NODE_COLORS.EXTENSION },
    { label: 'Scheduler', color: NODE_COLORS.SCHEDULER },
    { label: 'Subagent', color: NODE_COLORS.SUBAGENT_SURFACE },
  ]

  return (
    <>
      <div ref={containerRef} className="scan-topology-canvas" />
      <div style={{ display: 'flex', gap: 16, padding: '8px 16px', flexWrap: 'wrap', fontSize: 11, color: 'var(--gray-400)' }}>
        {legend.map(l => (
          <span key={l.label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: l.color, display: 'inline-block' }} />
            {l.label}
          </span>
        ))}
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 12 }}>
          {Object.entries(RISK_BORDER).map(([sev, r]) => (
            <span key={sev} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', border: `2px solid ${r.color}`, display: 'inline-block' }} />
              {sev}
            </span>
          ))}
        </span>
      </div>
    </>
  )
}
