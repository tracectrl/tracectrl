import { useEffect, useState, useMemo, useCallback, useRef } from 'react'
import { fetchLatestScan, ScanResult, ScanTopology, ScanDetail, triggerScan, pollScanStatus } from '../api/scan'
import ScanTopologyCanvas, { SelectedNode } from '../components/ScanTopologyCanvas'
import ScanNodePanel from '../components/ScanNodePanel'
import ScanFindingsPanel from '../components/ScanFindingsPanel'

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
  const [scanData, setScanData] = useState<ScanDetail | null>(null)
  const [rescanning, setRescanning] = useState(false)
  const topologyRef = useRef<HTMLDivElement>(null)

  useEffect(() => { document.title = 'Scan Report \u2014 TraceCtrl' }, [])

  const loadData = useCallback(() => {
    setLoading(true)
    setError(null)
    fetchLatestScan()
      .then(data => {
        setScanId(data.scan_id)
        setResults(data.results)
        setTopology(data.topology ?? null)
        setScanData(data)
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

  const meta = results.length > 0 ? results[0] : null

  const handleRescan = useCallback(async () => {
    const path = meta?.openclaw_path
    if (!path) return
    setRescanning(true)
    try {
      const trigger = await triggerScan(path)
      const poll = setInterval(async () => {
        const status = await pollScanStatus(trigger.scan_id)
        if (status.status === 'complete' || status.status === 'failed') {
          clearInterval(poll)
          setRescanning(false)
          loadData()
        }
      }, 2000)
    } catch {
      setRescanning(false)
    }
  }, [meta, loadData])

  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Security</div>
        <h2>OpenClaw Security Scan</h2>
        <p className="page-meta" aria-live="polite">
          {loading
            ? 'Loading scan results...'
            : scanId
              ? `Scan ${scanId} \u2014 ${meta?.scanned_at ?? ''} \u2014 ${meta?.openclaw_path ?? ''}`
              : 'No scans available'}
        </p>
        {!loading && results.length > 0 && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={handleRescan}
            disabled={rescanning}
            style={{ marginTop: 'var(--space-2)' }}
          >
            {rescanning ? 'Scanning…' : 'Rescan'}
          </button>
        )}
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

      {!loading && scanData?.config_changed && (
        <div className="config-drift-banner config-drift-banner--changed">
          <span>⚠ OpenClaw config has changed since last scan</span>
          <button className="btn btn-sm" onClick={handleRescan} disabled={rescanning}>
            {rescanning ? 'Scanning…' : 'Rescan Now'}
          </button>
        </div>
      )}

      {!loading && !scanData?.config_changed && (scanData?.days_since_scan ?? 0) > 7 && (
        <div className="config-drift-banner config-drift-banner--stale">
          <span>Last scan was {scanData?.days_since_scan} days ago — consider rescanning</span>
          <button className="btn btn-ghost btn-sm" onClick={handleRescan} disabled={rescanning}>
            Rescan Now
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
          {/* Severity summary cards */}
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

          {/* Topology visualization */}
          {topology && topology.nodes.length > 0 && (
            <div className="scan-topology-panel" ref={topologyRef}>
              <div className="scan-topology-header">
                <span>Architecture Risk View</span>
                <span>{topology.nodes.length} nodes · {topology.edges.length} edges</span>
              </div>
              <ScanTopologyCanvas
                topology={topology}
                nodeRiskMap={nodeRiskMap}
                onNodeClick={(n) => setSelectedNode(n ?? null)}
                selectedNodeId={selectedNode?.id ?? null}
              />
            </div>
          )}

          <ScanFindingsPanel
            results={results}
            topology={topology}
            workspacePath={meta?.openclaw_path ?? ''}
            onRescan={handleRescan}
            onFixApplied={() => loadData()}
            showSeverityCards={false}
          />
        </>
      )}
      <ScanNodePanel node={selectedNode} onClose={() => setSelectedNode(null)} />
    </div>
  )
}
