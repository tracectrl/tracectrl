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

  const agentCount = graph?.nodes.filter(n => n.type === 'agent').length ?? 0
  const toolCount = graph?.nodes.filter(n => n.type === 'tool').length ?? 0

  return (
    <div>
      <div className="page-header flex justify-between items-center">
        <div>
          <div className="section-tag">Topology</div>
          <h2>Agent Topology</h2>
          <p className="page-meta">
            {loading
              ? 'Loading graph...'
              : graph
                ? `${agentCount} agents · ${toolCount} tools · ${graph.edges.length} connections`
                : 'No data'}
          </p>
        </div>
        {!loading && graph && (
          <div className="live-indicator">Live</div>
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}

      <GraphCanvas data={graph} onNodeSelect={handleNodeSelect} />
      <SidebarPanel node={selectedNode} onClose={() => setSelectedNode(null)} />
    </div>
  )
}
