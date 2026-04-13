import { useEffect, useState, useMemo, useCallback } from 'react'
import { fetchLatestScan, ScanResult, ScanTopology } from '../api/scan'
import ScanTopologyCanvas from '../components/ScanTopologyCanvas'

const SEVERITY_ORDER: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1, pass: 0 }

const CATEGORY_MAP: Record<string, string> = {
  'Network': 'Security',
  'Credentials': 'Security',
  'Tools': 'Security',
  'Ingress': 'Security',
  'Guardrails': 'Security',
  'Filesystem': 'Security',
  'Lateral Movement': 'Security',
  'Plugins': 'Security',
  'LLM Providers': 'Security',
  'Logging': 'Security',
  'Security': 'Security',
  'Operational': 'Operational',
  'Performance': 'Performance',
  'Compliance': 'Compliance',
}

const CATEGORY_ORDER = ['Security', 'Operational', 'Performance', 'Compliance']

const SECTION_PREFIX_MAP: Record<string, string[]> = {
  'Ingress': ['ingress:'],
  'Tools': ['tool:'],
  'LLM Providers': ['llm:'],
  'Lateral Movement': ['subagent_surface:'],
  'Persistence': ['scheduler:'],
  'Plugins': ['extension:'],
}
const AGENT_SECTIONS = new Set(['Network', 'Guardrails', 'Credentials', 'Filesystem', 'Logging'])
const SEV_RANK: Record<string, number> = { critical: 3, high: 2, medium: 1 }

function severityBadgeClass(severity: string): string {
  const s = severity.toLowerCase()
  if (s === 'critical') return 'badge-critical'
  if (s === 'high') return 'badge-high'
  if (s === 'medium') return 'badge-medium'
  return 'badge-low'
}

interface CategoryGroup {
  name: string
  total: number
  passed: number
  failed: number
  failedResults: ScanResult[]
  passedResults: ScanResult[]
}

export default function ScanReport() {
  const [results, setResults] = useState<ScanResult[]>([])
  const [scanId, setScanId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [topology, setTopology] = useState<ScanTopology | null>(null)
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set())
  const [showPassed, setShowPassed] = useState<Record<string, boolean>>({})

  useEffect(() => { document.title = 'Scan Report \u2014 TraceCtrl' }, [])

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

  const categoryGroups = useMemo(() => {
    const groupMap = new Map<string, { failed: ScanResult[]; passed: ScanResult[] }>()
    for (const cat of CATEGORY_ORDER) {
      groupMap.set(cat, { failed: [], passed: [] })
    }

    for (const r of results) {
      const category = CATEGORY_MAP[r.section] ?? 'Security'
      const group = groupMap.get(category)
      if (!group) continue
      if (r.passed === 1) {
        group.passed.push(r)
      } else {
        group.failed.push(r)
      }
    }

    // Sort failed by severity descending
    const sortBySeverity = (a: ScanResult, b: ScanResult) => {
      const aOrd = SEVERITY_ORDER[a.severity.toLowerCase()] ?? 0
      const bOrd = SEVERITY_ORDER[b.severity.toLowerCase()] ?? 0
      return bOrd - aOrd
    }

    const groups: CategoryGroup[] = []
    for (const name of CATEGORY_ORDER) {
      const g = groupMap.get(name)!
      g.failed.sort(sortBySeverity)
      groups.push({
        name,
        total: g.failed.length + g.passed.length,
        passed: g.passed.length,
        failed: g.failed.length,
        failedResults: g.failed,
        passedResults: g.passed,
      })
    }
    return groups.filter(g => g.total > 0)
  }, [results])

  // Auto-expand categories that have failures
  useEffect(() => {
    const withFailures = categoryGroups
      .filter(g => g.failed > 0)
      .map(g => g.name)
    setExpandedCategories(new Set(withFailures))
  }, [categoryGroups])

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

  const toggleCategory = (name: string) => {
    setExpandedCategories(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const toggleShowPassed = (category: string) => {
    setShowPassed(prev => ({ ...prev, [category]: !prev[category] }))
  }

  const meta = results.length > 0 ? results[0] : null

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
            <div className="scan-topology-panel">
              <div className="scan-topology-header">
                <span>Architecture Risk View</span>
                <span>{topology.nodes.length} nodes · {topology.edges.length} edges</span>
              </div>
              <ScanTopologyCanvas topology={topology} nodeRiskMap={nodeRiskMap} />
            </div>
          )}

          {/* Category sections */}
          <div style={{ marginTop: 'var(--space-6)' }}>
            {categoryGroups.map(group => {
              const expanded = expandedCategories.has(group.name)
              const passRatio = group.total > 0 ? Math.round((group.passed / group.total) * 100) : 0

              return (
                <div className="scan-category" key={group.name}>
                  <div
                    className="scan-category-header"
                    onClick={() => toggleCategory(group.name)}
                    role="button"
                    aria-expanded={expanded}
                  >
                    <span className="scan-category-name">{group.name}</span>
                    <span className="scan-category-ratio">
                      {group.passed}/{group.total} passed
                    </span>
                    <div className="scan-category-bar">
                      <div
                        className="scan-category-bar-fill"
                        style={{ width: `${passRatio}%` }}
                      />
                    </div>
                    <span className="scan-category-chevron">{expanded ? '\u25BC' : '\u25B6'}</span>
                  </div>
                  {expanded && (
                    <div className="scan-category-findings">
                      {group.failedResults.map(r => {
                        const isRowExpanded = expandedRow === r.check_id
                        return (
                          <div key={r.check_id}>
                            <div
                              className="scan-finding-row"
                              onClick={() => setExpandedRow(isRowExpanded ? null : r.check_id)}
                            >
                              <span className={`badge ${severityBadgeClass(r.severity)}`}>
                                {r.severity.toUpperCase()}
                              </span>
                              <span className="scan-finding-id">{r.check_id}</span>
                              <span className="scan-finding-title">{r.title}</span>
                            </div>
                            {isRowExpanded && (
                              <div className="scan-finding-detail">
                                <p>{r.finding}</p>
                                {r.remediation && (
                                  <p className="scan-finding-remediation">
                                    {r.remediation}
                                  </p>
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })}
                      {group.passed > 0 && (
                        <>
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => toggleShowPassed(group.name)}
                            style={{ marginTop: 'var(--space-2)' }}
                          >
                            {showPassed[group.name]
                              ? 'Hide passed'
                              : `Show ${group.passed} passed checks`}
                          </button>
                          {showPassed[group.name] && group.passedResults.map(r => {
                            const isRowExpanded = expandedRow === r.check_id
                            return (
                              <div key={r.check_id}>
                                <div
                                  className="scan-finding-row"
                                  onClick={() => setExpandedRow(isRowExpanded ? null : r.check_id)}
                                >
                                  <span className="badge badge-low">PASS</span>
                                  <span className="scan-finding-id">{r.check_id}</span>
                                  <span className="scan-finding-title">{r.title}</span>
                                </div>
                                {isRowExpanded && (
                                  <div className="scan-finding-detail">
                                    <p>{r.finding}</p>
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </>
                      )}
                      {group.failedResults.length === 0 && !showPassed[group.name] && (
                        <p style={{ fontSize: '13px', color: 'var(--gray-500)', margin: 0 }}>
                          All checks passed.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
