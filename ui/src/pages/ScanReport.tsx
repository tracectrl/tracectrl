import { useEffect, useState, useMemo, useCallback, useRef } from 'react'
import { fetchLatestScan, ScanResult, ScanTopology } from '../api/scan'
import ScanTopologyCanvas, { SelectedNode } from '../components/ScanTopologyCanvas'
import ScanNodePanel from '../components/ScanNodePanel'
import FindingsSection from '../components/findings/FindingsSection'

const SECTION_PREFIX_MAP: Record<string, string[]> = {
  'Ingress':          ['ingress:'],
  'Tools':            ['tool:'],
  'LLM Providers':    ['llm:'],
  'Lateral Movement': ['subagent_surface:'],
  'Persistence':      ['scheduler:'],
  'Plugins':          ['extension:'],
  'Skills':           ['skill:'],
}
const AGENT_SECTIONS = new Set(['Network', 'Guardrails', 'Credentials', 'Filesystem', 'Logging'])
const SEV_RANK: Record<string, number> = { critical: 3, high: 2, medium: 1 }

export default function ScanReport() {
  const [results, setResults] = useState<ScanResult[]>([])
  const [scanId, setScanId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [topology, setTopology] = useState<ScanTopology | null>(null)
  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null)
  const [showSkills, setShowSkills] = useState(true)
  const topologyRef = useRef<HTMLDivElement>(null)

  useEffect(() => { document.title = 'Scan Report — TraceCtrl' }, [])

  const loadData = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchLatestScan()
      .then(data => {
        setScanId(data.scan_id)
        setResults(data.results)
        setTopology(data.topology ?? null)
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const counts = useMemo(() => {
    let critical = 0, high = 0, medium = 0, passed = 0
    for (const r of results) {
      if (r.passed === 1) { passed++; continue }
      const s = r.severity.toLowerCase()
      if (s === 'critical') critical++
      else if (s === 'high') high++
      else if (s === 'medium') medium++
      else passed++
    }
    return { critical, high, medium, pass: passed }
  }, [results])

  const nodeRiskMap = useMemo(() => {
    const map = new Map<string, string>()
    if (!topology) return map
    for (const r of results) {
      if (r.passed === 1) continue
      const sev = r.severity.toLowerCase()
      const rank = SEV_RANK[sev] ?? 0
      if (rank === 0) continue

      const prefixes = SECTION_PREFIX_MAP[r.section]
      const targets: string[] = []
      if (prefixes) {
        topology.nodes.filter(n => prefixes.some(p => n.id.startsWith(p))).forEach(n => targets.push(n.id))
      }
      if (AGENT_SECTIONS.has(r.section)) {
        topology.nodes.filter(n => n.type === 'AGENT').forEach(n => targets.push(n.id))
      }
      for (const id of targets) {
        const existing = SEV_RANK[map.get(id) ?? ''] ?? 0
        if (rank > existing) map.set(id, sev)
      }
    }
    return map
  }, [results, topology])

  const filteredTopology = useMemo(() => {
    if (!topology) return null
    if (showSkills) return topology
    const skillNodeIds = new Set(
      topology.nodes.filter(n => n.type === 'SKILL').map(n => n.id)
    )
    return {
      ...topology,
      nodes: topology.nodes.filter(n => !skillNodeIds.has(n.id)),
      edges: topology.edges.filter(e =>
        !skillNodeIds.has(e.source) && !skillNodeIds.has(e.target)
      ),
    }
  }, [topology, showSkills])

  const meta = results.length > 0 ? results[0] : null

  const scrollToTopology = useCallback(() => {
    topologyRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [])

  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Security</div>
        <h2>OpenClaw Security Scan</h2>
        <p className="page-meta" aria-live="polite">
          {loading
            ? 'Loading scan results...'
            : scanId
              ? `Scan ${scanId} — ${meta?.scanned_at ?? ''} — ${meta?.openclaw_path ?? ''}`
              : 'No scans available'}
        </p>
      </div>

      {error && (
        <div className="error-banner">
          {error}
          <button
            className="btn btn-ghost btn-sm"
            style={{ marginLeft: 'auto' }}
            onClick={loadData}
          >
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <>
          <div className="scan-severity-grid">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="loading-skeleton" style={{ height: 90 }} />
            ))}
          </div>
          <div className="table-container">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="loading-skeleton" style={{ height: 44, marginBottom: 2 }} />
            ))}
          </div>
        </>
      ) : results.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <h3>No Scan Results Yet</h3>
          <p>Run an OpenClaw security scan to see compliance findings here.</p>
        </div>
      ) : (
        <>
          <div className="scan-severity-grid">
            <div className="scan-severity-card">
              <div className="scan-severity-count" style={{ color: 'var(--risk-critical)' }}>
                {counts.critical}
              </div>
              <div className="scan-severity-label">Critical</div>
            </div>
            <div className="scan-severity-card">
              <div className="scan-severity-count" style={{ color: 'var(--risk-high)' }}>
                {counts.high}
              </div>
              <div className="scan-severity-label">High</div>
            </div>
            <div className="scan-severity-card">
              <div className="scan-severity-count" style={{ color: 'var(--risk-medium)' }}>
                {counts.medium}
              </div>
              <div className="scan-severity-label">Medium</div>
            </div>
            <div className="scan-severity-card">
              <div className="scan-severity-count" style={{ color: 'var(--risk-low)' }}>
                {counts.pass}
              </div>
              <div className="scan-severity-label">Pass</div>
            </div>
          </div>

          {topology && topology.nodes.length > 0 && (
            <div className="scan-topology-panel" ref={topologyRef}>
              <div className="scan-topology-header">
                <span>Architecture Risk View</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <button
                    className={`phase-toggle${showSkills ? ' active' : ''}`}
                    onClick={() => setShowSkills(prev => !prev)}
                    style={{ fontSize: '12px', padding: '4px 10px' }}
                  >
                    {showSkills ? 'Hide Skills' : 'Show Skills'}
                  </button>
                  <span>{filteredTopology?.nodes.length ?? 0} nodes · {filteredTopology?.edges.length ?? 0} edges</span>
                </div>
              </div>
              <ScanTopologyCanvas
                topology={filteredTopology!}
                nodeRiskMap={nodeRiskMap}
                onNodeClick={(n) => setSelectedNode(n ?? null)}
                selectedNodeId={selectedNode?.id ?? null}
              />
            </div>
          )}

          <FindingsSection
            results={results}
            topology={topology}
            workspacePath={meta?.openclaw_path ?? ''}
            onRescan={loadData}
            onSelectNode={setSelectedNode}
            onScrollToTopology={scrollToTopology}
            onFixApplied={() => loadData()}
          />
        </>
      )}
      <ScanNodePanel node={selectedNode} onClose={() => setSelectedNode(null)} />
    </div>
  )
}
