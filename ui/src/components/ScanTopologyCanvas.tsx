import { useEffect, useRef } from 'react'
import cytoscape, { Core } from 'cytoscape'
import dagre from 'cytoscape-dagre'
import { ScanTopology } from '../api/scan'

cytoscape.use(dagre)

// Neon accent colours — used for borders + legend
const NODE_COLORS: Record<string, string> = {
  INGRESS:          '#00D4FF', // cyan       — internet-facing gateway
  AGENT:            '#4D9EFF', // electric blue — core processor
  TOOL:             '#00E676', // neon green — utility function
  LLM_PROVIDER:     '#C87FFF', // violet     — AI model
  SCHEDULER:        '#FFB74D', // amber      — time-based trigger
  EXTENSION:        '#FF7043', // deep orange — plugin
  SUBAGENT_SURFACE: '#FF4081', // hot pink   — multi-agent surface
  STORAGE:          '#78909C', // steel      — data store
  EXTERNAL_SERVICE: '#78909C', // steel
  SKILL:            '#FF4DB8', // magenta    — third-party integration
}

// Dark interior fills — lets the neon border pop
const NODE_BG: Record<string, string> = {
  INGRESS:          '#001A22',
  AGENT:            '#010D1C',
  TOOL:             '#001A0A',
  LLM_PROVIDER:     '#10082A',
  SCHEDULER:        '#1C1200',
  EXTENSION:        '#1C0800',
  SUBAGENT_SURFACE: '#1C0014',
  STORAGE:          '#0C1218',
  EXTERNAL_SERVICE: '#0C1218',
  SKILL:            '#1C0018',
}

// Per-type shape + dimensions
interface NodeStyle { shape: string; w: number; h: number; bw: number }
const NODE_TYPE_STYLES: Record<string, NodeStyle> = {
  INGRESS:          { shape: 'diamond',         w: 52, h: 52, bw: 3   },
  AGENT:            { shape: 'hexagon',          w: 46, h: 46, bw: 2.5 },
  TOOL:             { shape: 'cutrectangle',     w: 40, h: 30, bw: 2   },
  LLM_PROVIDER:     { shape: 'ellipse',          w: 42, h: 42, bw: 2.5 },
  SCHEDULER:        { shape: 'rectangle',        w: 44, h: 30, bw: 2   },
  EXTENSION:        { shape: 'barrel',           w: 34, h: 36, bw: 2   },
  SUBAGENT_SURFACE: { shape: 'pentagon',         w: 40, h: 40, bw: 2   },
  STORAGE:          { shape: 'roundrectangle',   w: 36, h: 28, bw: 1.5 },
  EXTERNAL_SERVICE: { shape: 'roundrectangle',   w: 36, h: 28, bw: 1.5 },
  SKILL:            { shape: 'tag',              w: 46, h: 30, bw: 2   },
}
const DEFAULT_STYLE: NodeStyle = { shape: 'ellipse', w: 36, h: 36, bw: 2 }

// Risk border colors mirror globals.css --risk-* tokens (can't read CSS vars from cytoscape styles)
const RISK_BORDER: Record<string, { color: string; width: number }> = {
  critical: { color: '#FF4D4D', width: 4 },
  high:     { color: '#FF6B35', width: 3 },
  medium:   { color: '#FFBB00', width: 3 },
}

const LEGEND: { label: string; type: string }[] = [
  { label: 'Ingress',   type: 'INGRESS'          },
  { label: 'Agent',     type: 'AGENT'            },
  { label: 'Tool',      type: 'TOOL'             },
  { label: 'LLM',       type: 'LLM_PROVIDER'     },
  { label: 'Skill',     type: 'SKILL'            },
  { label: 'Extension', type: 'EXTENSION'        },
  { label: 'Scheduler', type: 'SCHEDULER'        },
  { label: 'Subagent',  type: 'SUBAGENT_SURFACE' },
]

// Legend glyphs — dark fill + neon stroke, matching the actual Cytoscape shapes
function ShapeGlyph({ type, color }: { type: string; color: string }) {
  const fill = NODE_BG[type] ?? '#0a0e18'
  const sw   = 1.5
  switch (type) {
    case 'INGRESS':
      return (
        <svg width={13} height={13} viewBox="0 0 13 13">
          <polygon points="6.5,0.5 12.5,6.5 6.5,12.5 0.5,6.5" fill={fill} stroke={color} strokeWidth={sw} />
        </svg>
      )
    case 'AGENT':
      return (
        <svg width={13} height={13} viewBox="0 0 13 13">
          <polygon points="6.5,0.5 12,3.5 12,9.5 6.5,12.5 1,9.5 1,3.5" fill={fill} stroke={color} strokeWidth={sw} />
        </svg>
      )
    case 'TOOL':
      return (
        <svg width={14} height={11} viewBox="0 0 14 11">
          <polygon points="2,0.5 12,0.5 13.5,2 13.5,9 12,10.5 2,10.5 0.5,9 0.5,2" fill={fill} stroke={color} strokeWidth={sw} />
        </svg>
      )
    case 'LLM_PROVIDER':
      return (
        <svg width={13} height={13} viewBox="0 0 13 13">
          <circle cx={6.5} cy={6.5} r={5.5} fill={fill} stroke={color} strokeWidth={sw} />
        </svg>
      )
    case 'SCHEDULER':
      return (
        <svg width={14} height={10} viewBox="0 0 14 10">
          <rect x={0.75} y={0.75} width={12.5} height={8.5} fill={fill} stroke={color} strokeWidth={sw} />
        </svg>
      )
    case 'EXTENSION':
      return (
        <svg width={11} height={13} viewBox="0 0 11 13">
          <rect x={0.75} y={0.75} width={9.5} height={11.5} rx={3} fill={fill} stroke={color} strokeWidth={sw} />
        </svg>
      )
    case 'SUBAGENT_SURFACE':
      return (
        <svg width={13} height={13} viewBox="0 0 13 13">
          <polygon points="6.5,0.5 12.5,4.8 10.2,12.5 2.8,12.5 0.5,4.8" fill={fill} stroke={color} strokeWidth={sw} />
        </svg>
      )
    case 'SKILL':
      return (
        <svg width={14} height={10} viewBox="0 0 14 10">
          <polygon points="0.5,0.5 10,0.5 13.5,5 10,9.5 0.5,9.5" fill={fill} stroke={color} strokeWidth={sw} />
        </svg>
      )
    default:
      return (
        <svg width={12} height={12} viewBox="0 0 12 12">
          <rect x={0.75} y={0.75} width={10.5} height={10.5} rx={2} fill={fill} stroke={color} strokeWidth={sw} />
        </svg>
      )
  }
}

export interface SelectedNode {
  id: string
  label: string
  nodeType: string
  properties: Record<string, unknown>
}

interface ScanTopologyCanvasProps {
  topology: ScanTopology
  nodeRiskMap: Map<string, string>
  onNodeClick?: (node: SelectedNode) => void
  selectedNodeId?: string | null
}

export default function ScanTopologyCanvas({ topology, nodeRiskMap, onNodeClick, selectedNodeId }: ScanTopologyCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)

  useEffect(() => {
    if (!containerRef.current || topology.nodes.length === 0) return

    if (cyRef.current) {
      cyRef.current.destroy()
      cyRef.current = null
    }

    const elements: cytoscape.ElementDefinition[] = []
    const ingressTypes = new Set(['INGRESS', 'SCHEDULER'])

    // Add invisible anchor node to force ingress nodes to the left
    elements.push({
      data: { id: '__anchor__', label: '', nodeType: '__anchor__' },
    })

    for (const node of topology.nodes) {
      elements.push({
        data: { id: node.id, label: node.label, nodeType: node.type, properties: node.properties ?? {} },
      })

      // Add invisible edge from anchor to all ingress nodes to force them left
      if (ingressTypes.has(node.type)) {
        elements.push({
          data: {
            id: `__anchor_to_${node.id}`,
            source: '__anchor__',
            target: node.id,
            edgeType: '__anchor__',
          },
        })
      }
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

    const typeStyles = Object.keys(NODE_COLORS).map(type => {
      const s = NODE_TYPE_STYLES[type] ?? DEFAULT_STYLE
      return {
        selector: `node[nodeType="${type}"]`,
        style: {
          'background-color': NODE_BG[type] ?? '#0a0e18',
          'shape': s.shape as any,
          'width': s.w,
          'height': s.h,
          'border-color': NODE_COLORS[type],
          'border-width': s.bw,
          'border-opacity': 0.95,
          'text-outline-width': 0,
        } as cytoscape.Css.Node,
      }
    })

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#0a0e18',
            'shape': 'ellipse',
            'label': 'data(label)',
            'color': '#A8C0D6',
            'font-size': '10px',
            'font-weight': 500 as any,
            'font-family': "'JetBrains Mono', 'Courier New', monospace",
            'text-valign': 'bottom',
            'text-margin-y': 9,
            'width': DEFAULT_STYLE.w,
            'height': DEFAULT_STYLE.h,
            'border-width': 2,
            'border-color': 'rgba(255,255,255,0.15)',
            'text-background-color': '#050810',
            'text-background-opacity': 0.9,
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
          },
        },
        ...typeStyles,
        {
          selector: 'edge',
          style: {
            'width': 1,
            'line-color': '#1A3040',
            'target-arrow-color': '#2A4A60',
            'target-arrow-shape': 'vee',
            'curve-style': 'bezier',
            'arrow-scale': 1,
            'label': 'data(label)',
            'font-size': '9px',
            'font-family': "'JetBrains Mono', monospace",
            'color': '#3A5A70',
            'text-background-color': '#050810',
            'text-background-opacity': 0.85,
            'text-background-padding': '2px',
            'text-background-shape': 'roundrectangle',
            'text-rotation': 'autorotate',
          } as cytoscape.Css.Edge,
        },
        // Hide anchor node and edges
        {
          selector: 'node[nodeType="__anchor__"]',
          style: {
            'visibility': 'hidden',
            'width': 1,
            'height': 1,
          } as cytoscape.Css.Node,
        },
        {
          selector: 'edge[edgeType="__anchor__"]',
          style: {
            'visibility': 'hidden',
          } as cytoscape.Css.Edge,
        },
      ],
      layout: {
        name: 'dagre',
        rankDir: 'LR',
        nodeSep: 80,
        rankSep: 150,
        animate: false,
      } as any,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
    })

    // Node click → lift state up
    cyRef.current.on('tap', 'node', (evt) => {
      const d = evt.target.data()
      onNodeClick?.({ id: d.id, label: d.label, nodeType: d.nodeType, properties: d.properties ?? {} })
    })
    // Click on background → deselect
    cyRef.current.on('tap', (evt) => {
      if (evt.target === cyRef.current) onNodeClick?.(null as any)
    })

    return () => {
      cyRef.current?.destroy()
      cyRef.current = null
    }
  }, [topology, onNodeClick])

  // Highlight selected node
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.startBatch()
    cy.nodes().style({ 'overlay-opacity': 0 })
    if (selectedNodeId) {
      const node = cy.getElementById(selectedNodeId)
      const nodeType = node.data('nodeType') as string
      const glowColor = NODE_COLORS[nodeType] ?? '#4D9EFF'
      node.style({ 'overlay-color': glowColor, 'overlay-opacity': 0.2, 'overlay-padding': 8 })
    }
    cy.endBatch()
  }, [selectedNodeId, topology])

  // Apply risk border overrides
  useEffect(() => {
    const cy = cyRef.current
    if (!cy || nodeRiskMap.size === 0) return

    cy.startBatch()
    for (const [nodeId, severity] of nodeRiskMap) {
      const node = cy.getElementById(nodeId)
      if (node.length === 0) continue
      const risk = RISK_BORDER[severity]
      if (risk) {
        node.style({ 'border-width': risk.width, 'border-color': risk.color })
      }
    }
    cy.endBatch()
  }, [nodeRiskMap, topology])

  return (
    <>
      <div ref={containerRef} className="scan-topology-canvas" />
      <div className="scan-topology-legend">
        {LEGEND.map(l => (
          <span key={l.label} className="legend-item">
            <ShapeGlyph type={l.type} color={NODE_COLORS[l.type]} />
            <span style={{ color: NODE_COLORS[l.type], opacity: 0.85 }}>{l.label}</span>
          </span>
        ))}
        <span className="legend-risk-group">
          {Object.entries(RISK_BORDER).map(([sev, r]) => (
            <span key={sev} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{
                width: 7, height: 7, borderRadius: '50%',
                border: `1.5px solid ${r.color}`,
                boxShadow: `0 0 4px ${r.color}66`,
                display: 'inline-block',
              }} />
              <span style={{ color: r.color, opacity: 0.8 }}>{sev}</span>
            </span>
          ))}
        </span>
      </div>
    </>
  )
}
