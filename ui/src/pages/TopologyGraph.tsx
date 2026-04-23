import { useEffect, useState, useCallback, useMemo } from 'react'
import GraphCanvas from '../components/GraphCanvas'
import SidebarPanel from '../components/SidebarPanel'
import PhaseReplaySlider from '../components/PhaseReplaySlider'
import AttackFindingsPanel from '../components/AttackFindingsPanel'
import EmptyState from '../components/shared/EmptyState'
import ErrorBanner from '../components/shared/ErrorBanner'
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
  const [perspective, setPerspective] = useState<'developer' | 'attacker'>('developer')
  const [agentRisks, setAgentRisks] = useState<AgentRisk[]>([])
  const [replayNs, setReplayNs] = useState<number | null>(null)
  const [attackMode, setAttackMode] = useState(false)
  const [attackPaths, setAttackPaths] = useState<AttackPath[]>([])
  const [overlay, setOverlay] = useState<AttackOverlay | null>(null)
  const [selectedAttackPath, setSelectedAttackPath] = useState<AttackPath | null>(null)

  useEffect(() => { document.title = 'Topology — TraceCtrl' }, [])

  const load = useCallback(() => {
    setError(null)
    setLoading(true)
    fetchTopologyGraph(selectedProject)
      .then(setGraph)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
    fetchLatestSpans(selectedProject).then(setLatestSpans).catch(() => {})
    fetchAgentRisks(selectedProject).then(setAgentRisks).catch(() => {})
  }, [selectedProject])

  useEffect(() => { load() }, [load])

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

  const agentCount = graph?.nodes.filter(n => n.type === 'agent').length ?? 0
  const toolCount = graph?.nodes.filter(n => n.type === 'tool').length ?? 0

  const attackerView = perspective === 'attacker'

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
                ? `${agentCount} agents · ${toolCount} tools · ${graph.edges.length} connections`
                : 'No data'}
          </p>
        </div>
        {!loading && graph && (
          <div className="topo-controls">
            <div className="segmented" role="group" aria-label="Perspective">
              <button
                type="button"
                className={`segmented-btn${!attackerView ? ' is-active' : ''}`}
                onClick={() => setPerspective('developer')}
                aria-pressed={!attackerView}
              >
                Developer
              </button>
              <button
                type="button"
                className={`segmented-btn${attackerView ? ' is-active' : ''}`}
                onClick={() => setPerspective('attacker')}
                aria-pressed={attackerView}
              >
                Attacker
              </button>
            </div>

            <button
              type="button"
              className={`phase-toggle${attackMode ? ' active' : ''}`}
              onClick={() => setAttackMode(prev => !prev)}
              aria-pressed={attackMode}
            >
              Attack Surface
            </button>

            {latestSpans.length > 0 && (
              <label className="topo-phase-check">
                <input
                  type="checkbox"
                  checked={showPhases}
                  onChange={e => setShowPhases(e.target.checked)}
                />
                <span>Phases</span>
              </label>
            )}

            <div className="live-indicator">Live</div>
          </div>
        )}
      </div>

      {error && <ErrorBanner error={error} onRetry={load} />}

      {!loading && graph && graph.nodes.length === 0 && (
        <EmptyState
          title="No Topology Data"
          hint="Agent topology will appear here once your instrumented agents start sending traces."
        />
      )}

      <GraphCanvas
        data={graph}
        onNodeSelect={handleNodeSelect}
        highlightedNodeIds={highlightedNodeIds}
        phaseGroups={phases}
        showPhases={showPhases}
        attackerView={attackerView}
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
