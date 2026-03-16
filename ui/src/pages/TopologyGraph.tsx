import { useEffect, useState, useCallback } from 'react'
import GraphCanvas from '../components/GraphCanvas'
import SidebarPanel from '../components/SidebarPanel'
import { fetchTopologyGraph, TopologyGraph, TopologyNode } from '../api/client'

export default function TopologyGraphPage() {
  const [graph, setGraph] = useState<TopologyGraph | null>(null)
  const [selectedNode, setSelectedNode] = useState<TopologyNode | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchTopologyGraph()
      .then(setGraph)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const handleNodeSelect = useCallback((node: TopologyNode | null) => {
    setSelectedNode(node)
  }, [])

  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Topology</div>
        <h2>Agent Topology</h2>
        <p className="page-meta">
          {loading
            ? 'Loading graph...'
            : graph
              ? `${graph.nodes.length} nodes · ${graph.edges.length} edges`
              : 'No data'}
        </p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <GraphCanvas data={graph} onNodeSelect={handleNodeSelect} />
      <SidebarPanel node={selectedNode} onClose={() => setSelectedNode(null)} />
    </div>
  )
}
