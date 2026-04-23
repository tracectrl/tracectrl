import { useCallback, useEffect, useMemo, useState } from 'react'
import { ScanResult, ScanTopology, applyFixes } from '../../api/scan'
import { SelectedNode } from '../ScanTopologyCanvas'
import { AUTO_FIXABLE_IDS } from '../../data/fixSnippets'
import FindingsTabs, { TabStat } from './FindingsTabs'
import FindingCard from './FindingCard'
import FindingDrawer from './FindingDrawer'

const SEVERITY_ORDER: Record<string, number> = {
  critical: 4, high: 3, medium: 2, low: 1, pass: 0,
}

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

function findNodeForResult(result: ScanResult, topology: ScanTopology | null): SelectedNode | null {
  if (!topology) return null
  const prefixes = SECTION_PREFIX_MAP[result.section]
  let node = prefixes
    ? topology.nodes.find(n => prefixes.some(p => n.id.startsWith(p))) ?? null
    : null
  if (!node && AGENT_SECTIONS.has(result.section)) {
    node = topology.nodes.find(n => n.type === 'AGENT') ?? null
  }
  if (!node) return null
  return { id: node.id, label: node.label, nodeType: node.type, properties: node.properties }
}

type SeverityFilter = 'all' | 'critical' | 'high' | 'medium'

interface Props {
  results: ScanResult[]
  topology: ScanTopology | null
  workspacePath: string
  onRescan: () => void
  onSelectNode: (node: SelectedNode | null) => void
  onScrollToTopology: () => void
  onFixApplied: (ids: string[]) => void
}

export default function FindingsSection({
  results,
  topology,
  workspacePath,
  onRescan,
  onSelectNode,
  onScrollToTopology,
  onFixApplied,
}: Props) {
  const [activeTab, setActiveTab] = useState<string>('all')
  const [severity, setSeverity] = useState<SeverityFilter>('all')
  const [showPassed, setShowPassed] = useState(false)
  const [openId, setOpenId] = useState<string | null>(null)
  const [focusedId, setFocusedId] = useState<string | null>(null)
  const [fixedIds, setFixedIds] = useState<Set<string>>(new Set())
  const [fixingId, setFixingId] = useState<string | null>(null)
  const [fixingAll, setFixingAll] = useState(false)
  const [fixError, setFixError] = useState<string | null>(null)

  // Category for each result, plus a stable sorted list grouped by category.
  const categoryOf = useCallback(
    (r: ScanResult) => CATEGORY_MAP[r.section] ?? 'Security',
    []
  )

  const sortResults = useCallback((a: ScanResult, b: ScanResult) => {
    const aOrd = SEVERITY_ORDER[a.severity.toLowerCase()] ?? 0
    const bOrd = SEVERITY_ORDER[b.severity.toLowerCase()] ?? 0
    if (bOrd !== aOrd) return bOrd - aOrd
    return a.check_id.localeCompare(b.check_id)
  }, [])

  // Category stats for tabs
  const tabs = useMemo<TabStat[]>(() => {
    const counts = new Map<string, { total: number; failed: number }>()
    for (const cat of CATEGORY_ORDER) counts.set(cat, { total: 0, failed: 0 })
    let total = 0
    let failed = 0
    for (const r of results) {
      const cat = categoryOf(r)
      const c = counts.get(cat)
      if (!c) continue
      c.total++
      total++
      if (r.passed !== 1) { c.failed++; failed++ }
    }
    const out: TabStat[] = [{ key: 'all', label: 'All', total, failed }]
    for (const cat of CATEGORY_ORDER) {
      const c = counts.get(cat)!
      if (c.total === 0) continue
      out.push({ key: cat, label: cat, total: c.total, failed: c.failed })
    }
    return out
  }, [results, categoryOf])

  // Filtered + sorted visible list driving the grid
  const visible = useMemo(() => {
    const filtered = results.filter(r => {
      if (activeTab !== 'all' && categoryOf(r) !== activeTab) return false
      if (r.passed === 1) return showPassed
      if (severity !== 'all' && r.severity.toLowerCase() !== severity) return false
      return true
    })
    filtered.sort(sortResults)
    return filtered
  }, [results, activeTab, severity, showPassed, categoryOf, sortResults])

  // Auto-open drawer navigation (j/k, arrow)
  const openResult = visible.find(r => r.check_id === openId) ?? null
  const openIndex = openResult ? visible.findIndex(r => r.check_id === openResult.check_id) : -1

  const openCard = useCallback(
    (r: ScanResult) => {
      setOpenId(r.check_id)
      setFocusedId(r.check_id)
      const node = findNodeForResult(r, topology)
      if (node) {
        onSelectNode(node)
        onScrollToTopology()
      } else {
        onSelectNode(null)
      }
    },
    [topology, onSelectNode, onScrollToTopology]
  )

  const closeDrawer = useCallback(() => {
    setOpenId(null)
    onSelectNode(null)
  }, [onSelectNode])

  const openPrev = useMemo(() => {
    if (openIndex <= 0) return undefined
    return () => openCard(visible[openIndex - 1])
  }, [openIndex, visible, openCard])

  const openNext = useMemo(() => {
    if (openIndex < 0 || openIndex >= visible.length - 1) return undefined
    return () => openCard(visible[openIndex + 1])
  }, [openIndex, visible, openCard])

  // Grid-level keyboard: when drawer closed, arrow/j/k moves focus; Enter opens.
  useEffect(() => {
    if (openId) return
    const onKey = (e: KeyboardEvent) => {
      if (visible.length === 0) return
      const target = e.target as HTMLElement | null
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return

      const idx = focusedId
        ? Math.max(0, visible.findIndex(r => r.check_id === focusedId))
        : -1

      if (e.key === 'ArrowDown' || e.key === 'j') {
        const next = visible[Math.min(visible.length - 1, idx + 1)]
        if (next) { setFocusedId(next.check_id); e.preventDefault() }
      } else if (e.key === 'ArrowUp' || e.key === 'k') {
        const prev = visible[Math.max(0, idx - 1)]
        if (prev) { setFocusedId(prev.check_id); e.preventDefault() }
      } else if (e.key === 'Enter' && focusedId) {
        const r = visible.find(x => x.check_id === focusedId)
        if (r) { openCard(r); e.preventDefault() }
      } else if (e.key === 'f') {
        setShowPassed(p => !p)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [openId, visible, focusedId, openCard])

  // Ensure focused card stays in the visible list when filters change.
  useEffect(() => {
    if (focusedId && !visible.find(r => r.check_id === focusedId)) {
      setFocusedId(visible[0]?.check_id ?? null)
    }
  }, [visible, focusedId])

  const unfixedAutoFixable = useMemo(
    () => results.filter(r => r.passed !== 1 && AUTO_FIXABLE_IDS.has(r.check_id) && !fixedIds.has(r.check_id)),
    [results, fixedIds]
  )

  const handleFix = useCallback(
    async (ids: string[]) => {
      if (ids.length === 0) return
      setFixError(null)
      if (ids.length === 1) setFixingId(ids[0])
      else setFixingAll(true)
      try {
        const res = await applyFixes(workspacePath, ids)
        const next = new Set(fixedIds)
        for (const id of res.applied) next.add(id)
        setFixedIds(next)
        onFixApplied(res.applied)
      } catch (e) {
        setFixError(e instanceof Error ? e.message : 'Fix failed')
      } finally {
        setFixingId(null)
        setFixingAll(false)
      }
    },
    [workspacePath, fixedIds, onFixApplied]
  )

  const showEmpty = visible.length === 0

  return (
    <section className="findings-section">
      <div className="findings-chrome">
        <FindingsTabs tabs={tabs} active={activeTab} onChange={setActiveTab} />
        <div className="findings-controls">
          <div className="findings-sevfilter" role="group" aria-label="Severity filter">
            {(['all', 'critical', 'high', 'medium'] as SeverityFilter[]).map(s => (
              <button
                key={s}
                className={`findings-sevchip chip-${s}${severity === s ? ' is-active' : ''}`}
                onClick={() => setSeverity(s)}
              >
                {s === 'all' ? 'All' : s[0].toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
          <label className="findings-passtoggle">
            <input
              type="checkbox"
              checked={showPassed}
              onChange={e => setShowPassed(e.target.checked)}
            />
            <span>Show passed</span>
          </label>
          {unfixedAutoFixable.length > 0 && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => handleFix(unfixedAutoFixable.map(r => r.check_id))}
              disabled={fixingAll}
            >
              {fixingAll ? 'Fixing…' : `Fix All (${unfixedAutoFixable.length})`}
            </button>
          )}
          <button className="btn btn-ghost btn-sm" onClick={onRescan}>Rescan</button>
        </div>
      </div>

      {fixError && (
        <div className="error-banner" style={{ marginTop: 'var(--space-3)' }}>{fixError}</div>
      )}

      {showEmpty ? (
        <div className="findings-empty">
          <p>No findings match these filters.</p>
          <p className="findings-empty-hint">
            {severity !== 'all' && <>Try severity <button className="link-btn" onClick={() => setSeverity('all')}>All</button>. </>}
            {!showPassed && <>Or <button className="link-btn" onClick={() => setShowPassed(true)}>show passed checks</button>.</>}
          </p>
        </div>
      ) : (
        <div className="findings-grid" role="list">
          {visible.map(r => {
            const cat = categoryOf(r)
            const autoFixable = AUTO_FIXABLE_IDS.has(r.check_id)
            const fixed = fixedIds.has(r.check_id)
            return (
              <div role="listitem" key={r.check_id}>
                <FindingCard
                  result={r}
                  category={cat}
                  autoFixable={autoFixable}
                  fixed={fixed}
                  focused={focusedId === r.check_id}
                  onOpen={() => openCard(r)}
                  onFocus={() => setFocusedId(r.check_id)}
                />
              </div>
            )
          })}
        </div>
      )}

      <div className="findings-kbdhint" aria-hidden="true">
        <kbd>↑</kbd><kbd>↓</kbd> navigate · <kbd>↵</kbd> open · <kbd>Esc</kbd> close · <kbd>f</kbd> toggle passed
      </div>

      <FindingDrawer
        result={openResult}
        category={openResult ? categoryOf(openResult) : ''}
        autoFixable={openResult ? AUTO_FIXABLE_IDS.has(openResult.check_id) : false}
        fixed={openResult ? fixedIds.has(openResult.check_id) : false}
        fixing={!!openResult && fixingId === openResult.check_id}
        open={!!openResult}
        onClose={closeDrawer}
        onFix={id => handleFix([id])}
        onPrev={openPrev}
        onNext={openNext}
      />
    </section>
  )
}
