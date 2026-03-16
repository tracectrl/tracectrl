import { useEffect, useRef } from 'react'
import cytoscape, { Core } from 'cytoscape'
import { TopologyGraph, TopologyNode } from '../api/client'

interface GraphCanvasProps {
  data: TopologyGraph | null
  onNodeSelect: (node: TopologyNode | null) => void
}

export default function GraphCanvas({ data, onNodeSelect }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<Core | null>(null)

  useEffect(() => {
    if (!containerRef.current || !data) return

    const elements: cytoscape.ElementDefinition[] = [
      ...data.nodes.map(n => ({
        data: { id: n.id, label: n.label, nodeType: n.type, ...n.metadata },
      })),
      ...data.edges.map(e => ({
        data: { id: e.id, source: e.source, target: e.target, edgeType: e.type },
      })),
    ]

    if (cyRef.current) {
      cyRef.current.destroy()
    }

    const styles = getComputedStyle(document.documentElement)
    const red = styles.getPropertyValue('--red').trim() || '#FC0404'
    const jade = styles.getPropertyValue('--jade').trim() || '#40706C'
    const white = styles.getPropertyValue('--white').trim() || '#F5F5F5'
    const gray400 = styles.getPropertyValue('--gray-400').trim() || '#8A8A8A'
    const gray700 = styles.getPropertyValue('--gray-700').trim() || '#3A3A3A'
    const gray800 = styles.getPropertyValue('--gray-800').trim() || '#2A2A2A'
    const darkBorder = styles.getPropertyValue('--dark-border').trim() || '#222222'

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: 'node[nodeType="agent"]',
          style: {
            'background-color': jade,
            'label': 'data(label)',
            'color': white,
            'font-size': '11px',
            'font-family': "'Poppins', sans-serif",
            'text-valign': 'bottom',
            'text-margin-y': 8,
            'width': 40,
            'height': 40,
            'shape': 'ellipse',
            'border-width': 2,
            'border-color': darkBorder,
          },
        },
        {
          selector: 'node[nodeType="tool"]',
          style: {
            'background-color': gray800,
            'label': 'data(label)',
            'color': gray400,
            'font-size': '10px',
            'font-family': "'JetBrains Mono', monospace",
            'text-valign': 'bottom',
            'text-margin-y': 8,
            'width': 30,
            'height': 30,
            'shape': 'round-rectangle',
            'border-width': 1,
            'border-color': darkBorder,
          },
        },
        {
          selector: 'edge[edgeType="agent_to_agent"]',
          style: {
            'line-color': red,
            'target-arrow-color': red,
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'width': 2,
            'opacity': 0.8,
          },
        },
        {
          selector: 'edge[edgeType="agent_to_tool"]',
          style: {
            'line-color': gray700,
            'target-arrow-color': gray700,
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'width': 1,
            'opacity': 0.6,
          },
        },
        {
          selector: ':selected',
          style: {
            'border-color': red,
            'border-width': 3,
          },
        },
      ],
      layout: { name: 'cose', animate: false },
    })

    cyRef.current.on('tap', 'node', (evt) => {
      const nodeData = evt.target.data()
      const node = data.nodes.find(n => n.id === nodeData.id)
      onNodeSelect(node || null)
    })

    cyRef.current.on('tap', (evt) => {
      if (evt.target === cyRef.current) {
        onNodeSelect(null)
      }
    })

    return () => {
      cyRef.current?.destroy()
    }
  }, [data, onNodeSelect])

  return <div ref={containerRef} className="graph-canvas" />
}
