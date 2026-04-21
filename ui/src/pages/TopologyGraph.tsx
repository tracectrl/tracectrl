import { useEffect, useState, useCallback, useMemo } from 'react'
import GraphCanvas from '../components/GraphCanvas'
import SidebarPanel from '../components/SidebarPanel'
import PhaseReplaySlider from '../components/PhaseReplaySlider'
import AttackFindingsPanel from '../components/AttackFindingsPanel'
import { fetchTopologyGraph, TopologyGraph, TopologyNode, fetchAttackPaths, fetchAttackOverlay, AttackPath, AttackOverlay } from '../api/client'
import { fetchLatestSpans, SpanDetail } from '../api/sessions'
import { fetchAgentRisks, AgentRisk } from '../api/risk'
import { usePhaseInference } from '../hooks/usePhaseInference'
import { useProject } from '../context/ProjectContext'

export default function TopologyGraphPage() {
  const { selectedProject } = useProject()
  const [graph, setGraph] = useState<TopologyGraph | null>(null)
  const [selectedNode, setSelectedNode] = useState<TopologyNode | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [latestSpans, setLatestSpans] = useState<SpanDetail[]>([])
  const [showPhases, setShowPhases] = useState(false)
  const [showAttackerView, setShowAttackerView] = useState(false)
  const [agentRisks, setAgentRisks] = useState<AgentRisk[]>([])
  const [replayNs, setReplayNs] = useState<number | null>(null)
  const [attackMode, setAttackMode] = useState(false)
  const [attackPaths, setAttackPaths] = useState<AttackPath[]>([])
  const [overlay, setOverlay] = useState<AttackOverlay | null>(null)
  const [selectedAttackPath, setSelectedAttackPath] = useState<AttackPath | null>(null)
  const [showSkills, setShowSkills] = useState(true)

  useEffect(() => { document.title = 'Topology — TraceCtrl' }, [])

  useEffect(() => {
    setLoading(true)
    fetchTopologyGraph(selectedProject)
      .then(setGraph)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))

    fetchLatestSpans(selectedProject).then(setLatestSpans).catch(() => {})
    fetchAgentRisks(selectedProject).then(setAgentRisks).catch(() => {})
  }, [selectedProject])

  // Fetch attack data when attack mode is toggled on
  useEffect(() => {
    if (attackMode) {
      fetchAttackPaths().then(setAttackPaths).catch(() => {})
      fetchAttackOverlay().then(setOverlay).catch(() => {})
    }
  }, [attackMode])

  const handleNodeSelect = useCallback((node: TopologyNode | null) => {
    setSelectedNode(node)
  }, [])

  const phases = usePhaseInference(latestSpans)

  const traceStartNs = useMemo(() => {
    if (latestSpans.length === 0) return 0
    return Math.min(...latestSpans.map(s => s.start_ns))
  }, [latestSpans])

  const traceDurationNs = useMemo(() => {
    if (latestSpans.length === 0) return 0
    const endNs = Math.max(...latestSpans.map(s => s.start_ns + s.duration_ns))
    return endNs - traceStartNs
  }, [latestSpans, traceStartNs])

  const highlightedNodeIds = useMemo(() => {
    if (replayNs === null) return undefined
    const activeIds = new Set<string>()
    for (const span of latestSpans) {
      const spanEnd = span.start_ns + span.duration_ns
      if (span.start_ns <= replayNs && spanEnd >= replayNs) {
        const agentId =
          span.attributes['tracectrl.agent.id'] ||
          span.attributes['agno.agent.id'] ||
          span.attributes['tracectrl.agent.name'] ||
          span.attributes['agent.name'] ||
          span.span_name.replace('.run', '')
        if (agentId) {
          activeIds.add(agentId)
          activeIds.add(agentId.toLowerCase().replace(/\s+/g, '-'))
        }
      }
    }
    return activeIds.size > 0 ? activeIds : undefined
  }, [replayNs, latestSpans])

  const filteredGraph = useMemo(() => {
    if (!graph) return null
    if (showSkills) return graph

    // Filter out skill nodes
    const skillNodeIds = new Set(
      graph.nodes.filter(n => n.type === 'skill').map(n => n.id)
    )

    return {
      ...graph,
      nodes: graph.nodes.filter(n => !skillNodeIds.has(n.id)),
      edges: graph.edges.filter(e =>
        !skillNodeIds.has(e.source) && !skillNodeIds.has(e.target)
      ),
    }
  }, [graph, showSkills])

  const agentCount = graph?.nodes.filter(n => n.type === 'agent').length ?? 0
  const toolCount = graph?.nodes.filter(n => n.type === 'tool').length ?? 0
  const skillCount = graph?.nodes.filter(n => n.type === 'skill').length ?? 0

  return (
    <div>
      <div className="page-header flex justify-between items-center">
        <div>
          <div className="section-tag">Topology</div>
          <h2>Agent Topology</h2>
          <p className="page-meta" aria-live="polite">
            {loading
              ? 'Loading graph...'
              : graph
                ? `${agentCount} agents · ${toolCount} tools · ${skillCount} skills · ${graph.edges.length} connections`
                : 'No data'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {!loading && graph && latestSpans.length > 0 && (
            <button
              className={`phase-toggle${showPhases ? ' active' : ''}`}
              onClick={() => setShowPhases(prev => !prev)}
              aria-pressed={showPhases}
            >
              Show Phases
            </button>
          )}
          {!loading && graph && (
            <button
              className={`phase-toggle${showAttackerView ? ' active' : ''}`}
              onClick={() => setShowAttackerView(v => !v)}
              aria-pressed={showAttackerView}
            >
              {showAttackerView ? 'Attacker View' : 'Developer View'}
            </button>
          )}
          {!loading && graph && (
            <button
              className={`phase-toggle${attackMode ? ' active' : ''}`}
              onClick={() => setAttackMode(prev => !prev)}
            >
              Attack Surface
            </button>
          )}
          {!loading && graph && (
            <button
              className={`phase-toggle${showSkills ? ' active' : ''}`}
              onClick={() => setShowSkills(prev => !prev)}
              aria-pressed={showSkills}
            >
              {showSkills ? 'Hide Skills' : 'Show Skills'}
            </button>
          )}
          {!loading && graph && (
            <div className="live-indicator">Live</div>
          )}
        </div>
      </div>

      {error && (
        <div className="error-banner">
          {error}
          <button className="btn btn-ghost btn-sm" style={{ marginLeft: 'auto' }} onClick={() => { setError(null); fetchTopologyGraph(selectedProject).then(setGraph).catch(err => setError(err.message)); fetchLatestSpans(selectedProject).then(setLatestSpans).catch(() => {}); }}>
            Retry
          </button>
        </div>
      )}

      {!loading && graph && graph.nodes.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" /><path d="M12 8v4M12 16h.01" />
            </svg>
          </div>
          <h3>No Topology Data</h3>
          <p>Agent topology will appear here once your instrumented agents start sending traces.</p>
        </div>
      )}

      <GraphCanvas
        data={filteredGraph}
        onNodeSelect={handleNodeSelect}
        highlightedNodeIds={highlightedNodeIds}
        phaseGroups={phases}
        showPhases={showPhases}
        attackerView={showAttackerView}
        agentRisks={agentRisks}
        attackMode={attackMode}
        overlay={overlay}
        selectedAttackPath={selectedAttackPath}
      />

      {latestSpans.length > 0 && traceDurationNs > 0 && (
        <PhaseReplaySlider
          traceStartNs={traceStartNs}
          traceDurationNs={traceDurationNs}
          currentNs={replayNs ?? traceStartNs}
          onChange={(ns) => setReplayNs(ns)}
          onClear={() => setReplayNs(null)}
        />
      )}

      {attackMode ? (
        <AttackFindingsPanel
          paths={attackPaths}
          selectedPath={selectedAttackPath}
          onPathSelect={setSelectedAttackPath}
          onClose={() => {
            setAttackMode(false)
            setSelectedAttackPath(null)
          }}
        />
      ) : (
        <SidebarPanel node={selectedNode} onClose={() => setSelectedNode(null)} />
      )}
    </div>
  )
}
