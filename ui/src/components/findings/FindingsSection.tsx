import { useCallback, useEffect, useMemo, useState } from 'react'
import { ScanResult, ScanTopology, applyFixes } from '../../api/scan'
import { SelectedNode } from '../ScanTopologyCanvas'
import { AUTO_FIXABLE_IDS } from '../../data/fixSnippets'
import { categorize, TopCategory, TOP_ORDER } from '../../data/checkCategories'
import FindingsTabs, { TabStat } from './FindingsTabs'
import FindingCard from './FindingCard'
import FindingDrawer from './FindingDrawer'
import AgentBriefDrawer from './AgentBriefDrawer'

const SEVERITY_ORDER: Record<string, number> = {
  critical: 4, high: 3, medium: 2, low: 1, pass: 0,
}

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
  const [briefOpen, setBriefOpen] = useState(false)

  const sortResults = useCallback((a: ScanResult, b: ScanResult) => {
    const aOrd = SEVERITY_ORDER[a.severity.toLowerCase()] ?? 0
    const bOrd = SEVERITY_ORDER[b.severity.toLowerCase()] ?? 0
    if (bOrd !== aOrd) return bOrd - aOrd
    return a.check_id.localeCompare(b.check_id)
  }, [])

  // Tab stats by top category
  const tabs = useMemo<TabStat[]>(() => {
    const counts = new Map<TopCategory, { total: number; failed: number }>()
    for (const t of TOP_ORDER) counts.set(t, { total: 0, failed: 0 })
    let total = 0
    let failed = 0
    for (const r of results) {
      const c = counts.get(categorize(r.check_id).top)
      if (!c) continue
      c.total++
      total++
      if (r.passed !== 1) { c.failed++; failed++ }
    }
    const out: TabStat[] = [{ key: 'all', label: 'All', total, failed }]
    for (const t of TOP_ORDER) {
      const c = counts.get(t)!
      if (c.total === 0) continue
      out.push({ key: t, label: t, total: c.total, failed: c.failed })
    }
    return out
  }, [results])

  // Filtered + sorted visible list driving the grid
  const visible = useMemo(() => {
    const filtered = results.filter(r => {
      if (activeTab !== 'all' && categorize(r.check_id).top !== activeTab) return false
      if (r.passed === 1) return showPassed
      if (severity !== 'all' && r.severity.toLowerCase() !== severity) return false
      return true
    })
    filtered.sort(sortResults)
    return filtered
  }, [results, activeTab, severity, showPassed, sortResults])

  // Group visible findings by sub-category, preserving subOrder for stable layout.
  const grouped = useMemo(() => {
    const map = new Map<string, { top: TopCategory; sub: string; subOrder: number; items: ScanResult[] }>()
    for (const r of visible) {
      const c = categorize(r.check_id)
      const key = `${c.top} :: ${c.sub}`
      const existing = map.get(key)
      if (existing) existing.items.push(r)
      else map.set(key, { top: c.top, sub: c.sub, subOrder: c.subOrder, items: [r] })
    }
    // Order groups by TopCategory then subOrder
    return Array.from(map.values()).sort((a, b) => {
      const aT = TOP_ORDER.indexOf(a.top)
      const bT = TOP_ORDER.indexOf(b.top)
      if (aT !== bT) return aT - bT
      return a.subOrder - b.subOrder
    })
  }, [visible])

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

  // Grid-level keyboard
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

  useEffect(() => {
    if (focusedId && !visible.find(r => r.check_id === focusedId)) {
      setFocusedId(visible[0]?.check_id ?? null)
    }
  }, [visible, focusedId])

  const unfixedAutoFixable = useMemo(
    () => results.filter(r => r.passed !== 1 && AUTO_FIXABLE_IDS.has(r.check_id) && !fixedIds.has(r.check_id)),
    [results, fixedIds]
  )

  // Non-auto-fixable failing findings — the pool for the agent brief button.
  const manualFailing = useMemo(
    () => results.filter(r => r.passed !== 1 && !AUTO_FIXABLE_IDS.has(r.check_id) && !fixedIds.has(r.check_id))
                 .sort(sortResults),
    [results, fixedIds, sortResults]
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

  const openBrief = useCallback(() => {
    if (manualFailing.length > 0) setBriefOpen(true)
  }, [manualFailing])

  const showEmpty = grouped.length === 0

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
          {manualFailing.length > 0 && (
            <button
              className="btn btn-ghost btn-sm agent-brief-btn"
              onClick={openBrief}
              title="Preview the markdown prompt for a coding agent, then copy"
            >
              Agent Brief ({manualFailing.length})
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
        <div className="findings-groups">
          {grouped.map(group => (
            <div className="findings-group" key={`${group.top}::${group.sub}`}>
              <div className="findings-group-head">
                <span className="findings-group-sub">{group.sub}</span>
                <span className="findings-group-top">{group.top}</span>
                <span className="findings-group-count">{group.items.length}</span>
              </div>
              <div className="findings-grid" role="list">
                {group.items.map(r => {
                  const autoFixable = AUTO_FIXABLE_IDS.has(r.check_id)
                  const fixed = fixedIds.has(r.check_id)
                  return (
                    <div role="listitem" key={r.check_id}>
                      <FindingCard
                        result={r}
                        category={group.sub}
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
            </div>
          ))}
        </div>
      )}

      <div className="findings-kbdhint" aria-hidden="true">
        <kbd>↑</kbd><kbd>↓</kbd> navigate · <kbd>↵</kbd> open · <kbd>Esc</kbd> close · <kbd>f</kbd> toggle passed
      </div>

      <FindingDrawer
        result={openResult}
        category={openResult ? categorize(openResult.check_id).sub : ''}
        autoFixable={openResult ? AUTO_FIXABLE_IDS.has(openResult.check_id) : false}
        fixed={openResult ? fixedIds.has(openResult.check_id) : false}
        fixing={!!openResult && fixingId === openResult.check_id}
        open={!!openResult}
        onClose={closeDrawer}
        onFix={id => handleFix([id])}
        onPrev={openPrev}
        onNext={openNext}
      />

      <AgentBriefDrawer
        open={briefOpen}
        onClose={() => setBriefOpen(false)}
        findings={manualFailing}
        workspacePath={workspacePath}
      />
    </section>
  )
}
