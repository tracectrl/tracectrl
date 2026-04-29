import { useEffect, useState, useCallback, useMemo } from 'react'
import GraphCanvas from '../components/GraphCanvas'
import SidebarPanel from '../components/SidebarPanel'
import PhaseReplaySlider from '../components/PhaseReplaySlider'
import AttackFindingsPanel from '../components/AttackFindingsPanel'
import EmptyState from '../components/shared/EmptyState'
import ErrorBanner from '../components/shared/ErrorBanner'
import AgentDetailPanel from '../components/AgentDetailPanel'
import { fetchTopologyGraph, TopologyGraph, TopologyNode, fetchAttackPaths, fetchAttackOverlay, AttackPath, AttackOverlay } from '../api/client'
import { fetchLatestSpans, fetchSessions, fetchTraceSpans, SpanDetail, SessionSummary, formatDuration } from '../api/sessions'
import { fetchAgentRisks, AgentRisk } from '../api/risk'
import { fetchAgentList, AgentSummary } from '../api/agents'
import { usePhaseInference } from '../hooks/usePhaseInference'
import { useProject } from '../context/ProjectContext'

export default function TopologyGraphPage() {
  const { selectedProject } = useProject()
  const [graph, setGraph] = useState<TopologyGraph | null>(null)
  const [selectedNode, setSelectedNode] = useState<TopologyNode | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<AgentSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // Replay state
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)
  const [replaySpans, setReplaySpans] = useState<SpanDetail[]>([])
  const [replayNs, setReplayNs] = useState<number | null>(null)

  const [showPhases, setShowPhases] = useState(false)
  const [perspective, setPerspective] = useState<'developer' | 'attacker'>('developer')
  const [agentRisks, setAgentRisks] = useState<AgentRisk[]>([])
  const [agents, setAgents] = useState<AgentSummary[]>([])
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
    fetchAgentRisks(selectedProject).then(setAgentRisks).catch(() => {})
    fetchAgentList(selectedProject).then(setAgents).catch(() => {})
    // Sessions feed the picker; default to latest.
    fetchSessions(selectedProject).then(list => {
      setSessions(list)
      if (list.length > 0 && !selectedTraceId) {
        setSelectedTraceId(list[0].trace_id)
      }
    }).catch(() => {})
  }, [selectedProject, selectedTraceId])

  useEffect(() => { load() }, [load])

  // Load spans for the picked session. Falls back to latest spans for the very
  // first render before the session list resolves.
  useEffect(() => {
    if (selectedTraceId) {
      fetchTraceSpans(selectedTraceId).then(setReplaySpans).catch(() => setReplaySpans([]))
    } else {
      fetchLatestSpans(selectedProject).then(setReplaySpans).catch(() => setReplaySpans([]))
    }
  }, [selectedTraceId, selectedProject])

  useEffect(() => {
    if (attackMode) {
      fetchAttackPaths().then(setAttackPaths).catch(() => {})
      fetchAttackOverlay().then(setOverlay).catch(() => {})
    }
  }, [attackMode])

  const handleNodeSelect = useCallback((node: TopologyNode | null) => {
    if (node?.type === 'agent') {
      // Resolve to a full AgentSummary so we can reuse <AgentDetailPanel>.
      const match =
        agents.find(a => a.agent_id === node.id) ||
        agents.find(a => a.name === node.label) ||
        agents.find(a => a.agent_id === node.label?.toLowerCase().replace(/\s+/g, '-'))
      if (match) {
        setSelectedAgent(match)
        setSelectedNode(null)
        return
      }
    }
    setSelectedNode(node)
    setSelectedAgent(null)
  }, [agents])

  const phases = usePhaseInference(replaySpans)

  const traceStartNs = useMemo(() => {
    if (replaySpans.length === 0) return 0
    return Math.min(...replaySpans.map(s => s.start_ns))
  }, [replaySpans])

  const traceDurationNs = useMemo(() => {
    if (replaySpans.length === 0) return 0
    const endNs = Math.max(...replaySpans.map(s => s.start_ns + s.duration_ns))
    return endNs - traceStartNs
  }, [replaySpans, traceStartNs])

  // WS3 bug fix: zero-duration spans (agent-as-tool delegation markers in
  // Strands sometimes produce these) were dropped by the strict `start <= ns
  // <= end` check at the trace tail. Treat zero-duration as a small point and
  // include them when the slider is at or past their start_ns.
  const highlightedNodeIds = useMemo(() => {
    if (replayNs === null) return undefined
    const traceEnd = traceStartNs + traceDurationNs
    const isAtMax = replayNs >= traceEnd
    const activeIds = new Set<string>()
    for (const span of replaySpans) {
      const dur = span.duration_ns
      const spanStart = span.start_ns
      const spanEnd = spanStart + dur
      const inWindow =
        dur === 0
          ? spanStart <= replayNs
          : (spanStart <= replayNs && spanEnd >= replayNs) ||
            // At the very end of the slider, include any span that ended
            // exactly at the trace boundary so the last node always lights up.
            (isAtMax && spanEnd === traceEnd)
      if (!inWindow) continue
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
    return activeIds.size > 0 ? activeIds : undefined
  }, [replayNs, replaySpans, traceStartNs, traceDurationNs])

  const agentCount = graph?.nodes.filter(n => n.type === 'agent').length ?? 0
  const toolCount = graph?.nodes.filter(n => n.type === 'tool').length ?? 0

  const attackerView = perspective === 'attacker'

  const formatSessionLabel = (s: SessionSummary) => {
    const t = new Date(s.start_time).toLocaleTimeString(undefined, {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
    return `${s.root_span_name || 'session'} · ${formatDuration(s.total_duration_ns)} · ${t}`
  }

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
            {sessions.length > 0 && (
              <div className="topo-session-picker">
                <label htmlFor="session-picker">Session</label>
                <select
                  id="session-picker"
                  value={selectedTraceId || ''}
                  onChange={e => {
                    setSelectedTraceId(e.target.value || null)
                    setReplayNs(null)
                  }}
                >
                  {sessions.slice(0, 50).map(s => (
                    <option key={s.trace_id} value={s.trace_id}>
                      {formatSessionLabel(s)}
                    </option>
                  ))}
                </select>
              </div>
            )}

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

            {replaySpans.length > 0 && (
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

      {replaySpans.length > 0 && traceDurationNs > 0 && (
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
        <>
          <AgentDetailPanel
            agent={selectedAgent}
            onClose={() => setSelectedAgent(null)}
          />
          <SidebarPanel
            node={selectedAgent ? null : selectedNode}
            onClose={() => setSelectedNode(null)}
          />
        </>
      )}
    </div>
  )
}
