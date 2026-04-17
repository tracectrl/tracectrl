import { useState, useMemo, useEffect } from 'react'
import { ScanResult, ScanTopology, applyFixes } from '../api/scan'
import { AUTO_FIXABLE_IDS } from '../data/fixSnippets'
import ConfigCodeBlock from './ConfigCodeBlock'

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
  'Skills': 'Security',
  'Persistence': 'Security',
  'Operational': 'Operational',
  'Performance': 'Performance',
  'Compliance': 'Compliance',
}

const CATEGORY_ORDER = ['Security', 'Operational', 'Performance', 'Compliance']

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

interface Props {
  results: ScanResult[]
  topology: ScanTopology | null
  workspacePath: string
  onRescan: () => void
  onFixApplied: (applied: string[]) => void
  showSeverityCards?: boolean
}

export default function ScanFindingsPanel({ results, topology: _topology, workspacePath, onRescan, onFixApplied, showSeverityCards = true }: Props) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null)
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set())
  const [showPassed, setShowPassed] = useState<Record<string, boolean>>({})
  const [fixedIds, setFixedIds] = useState<Set<string>>(new Set())
  const [fixingAll, setFixingAll] = useState(false)
  const [fixingId, setFixingId] = useState<string | null>(null)
  const [fixError, setFixError] = useState<string | null>(null)

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

  const unfixedAutoFixable = useMemo(() => {
    return results.filter(
      r => r.passed !== 1 && AUTO_FIXABLE_IDS.has(r.check_id) && !fixedIds.has(r.check_id)
    )
  }, [results, fixedIds])

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

  const handleFixOne = async (checkId: string) => {
    setFixingId(checkId)
    setFixError(null)
    try {
      const result = await applyFixes(workspacePath, [checkId])
      const newFixed = new Set(fixedIds)
      for (const id of result.applied) newFixed.add(id)
      setFixedIds(newFixed)
      onFixApplied(result.applied)
    } catch (e: unknown) {
      setFixError(e instanceof Error ? e.message : 'Fix failed')
    } finally {
      setFixingId(null)
    }
  }

  const handleFixAll = async () => {
    const ids = unfixedAutoFixable.map(r => r.check_id)
    if (ids.length === 0) return
    setFixingAll(true)
    setFixError(null)
    try {
      const result = await applyFixes(workspacePath, ids)
      const newFixed = new Set(fixedIds)
      for (const id of result.applied) newFixed.add(id)
      setFixedIds(newFixed)
      onFixApplied(result.applied)
    } catch (e: unknown) {
      setFixError(e instanceof Error ? e.message : 'Fix failed')
    } finally {
      setFixingAll(false)
    }
  }

  const meta = results.length > 0 ? results[0] : null

  return (
    <div>
      <div className="scan-findings-header">
        <div>
          <p className="page-meta">
            {meta ? `${meta.scanned_at} \u2014 ${meta.openclaw_path}` : ''}
          </p>
        </div>
        <div className="scan-findings-actions">
          {unfixedAutoFixable.length > 0 && (
            <button
              className="btn btn-primary btn-sm"
              onClick={handleFixAll}
              disabled={fixingAll}
            >
              {fixingAll ? 'Fixing\u2026' : `Fix All Auto-Fixable (${unfixedAutoFixable.length})`}
            </button>
          )}
          <button className="btn btn-ghost btn-sm" onClick={onRescan}>
            Rescan
          </button>
        </div>
      </div>

      {fixError && (
        <div className="error-banner" style={{ marginBottom: 'var(--space-4)' }}>
          {fixError}
        </div>
      )}

      {/* Severity summary cards */}
      {showSeverityCards && (
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
                    const isFixed = fixedIds.has(r.check_id)
                    const isAutoFixable = AUTO_FIXABLE_IDS.has(r.check_id)
                    const isFixingThis = fixingId === r.check_id

                    return (
                      <div key={r.check_id}>
                        <div
                          className="scan-finding-row"
                          onClick={() => setExpandedRow(isRowExpanded ? null : r.check_id)}
                        >
                          {isFixed ? (
                            <span className="badge badge-low" style={{ color: 'var(--risk-low)', background: 'color-mix(in srgb, var(--risk-low) 15%, transparent)' }}>
                              FIXED
                            </span>
                          ) : (
                            <span className={`badge ${severityBadgeClass(r.severity)}`}>
                              {r.severity.toUpperCase()}
                            </span>
                          )}
                          <span className="scan-finding-id">{r.check_id}</span>
                          <span className="scan-finding-title">{r.title}</span>
                          {isAutoFixable && !isFixed && (
                            <span
                              style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--gray-500)', flexShrink: 0 }}
                            >
                              auto-fixable
                            </span>
                          )}
                        </div>
                        {isRowExpanded && (
                          <div className="scan-finding-detail">
                            <p>{r.finding}</p>
                            {r.remediation && (
                              <p className="scan-finding-remediation">
                                {r.remediation}
                              </p>
                            )}
                            <ConfigCodeBlock checkId={r.check_id} />
                            {isAutoFixable && !isFixed && (
                              <button
                                className="btn btn-primary btn-sm"
                                onClick={e => { e.stopPropagation(); handleFixOne(r.check_id) }}
                                disabled={isFixingThis || fixingAll}
                                style={{ marginTop: 'var(--space-3)' }}
                              >
                                {isFixingThis ? 'Fixing\u2026' : 'Fix This'}
                              </button>
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
    </div>
  )
}
