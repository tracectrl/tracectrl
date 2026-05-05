import { useEffect, useState, useMemo, useCallback, useRef } from 'react'
import { fetchLatestScan, ScanResult, ScanTopology, triggerScan, pollScanStatus } from '../api/scan'
import ScanTopologyCanvas, { SelectedNode } from '../components/ScanTopologyCanvas'
import ScanNodePanel from '../components/ScanNodePanel'
import FindingsSection from '../components/findings/FindingsSection'
import EmptyState from '../components/shared/EmptyState'
import ErrorBanner from '../components/shared/ErrorBanner'
import ScanChangesNotification from '../components/ScanChangesNotification'
import { computeScanDiff, ScanDiff } from '../utils/scanDiff'

// Risk border colors removed - nodes stay at their type colors

export default function ScanReport() {
  const [results, setResults] = useState<ScanResult[]>([])
  const [scanId, setScanId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [topology, setTopology] = useState<ScanTopology | null>(null)
  const [highlightNode, setHighlightNode] = useState<SelectedNode | null>(null)
  const [panelNode, setPanelNode] = useState<SelectedNode | null>(null)
  const [showSkills, setShowSkills] = useState(true)
  const [rescanning, setRescanning] = useState(false)
  const [scanDiff, setScanDiff] = useState<ScanDiff | null>(null)
  const [newNodeIds, setNewNodeIds] = useState<Set<string>>(new Set())
  const topologyRef = useRef<HTMLDivElement>(null)
  const previousScanRef = useRef<{ topology: ScanTopology | null; results: ScanResult[] }>({
    topology: null,
    results: [],
  })

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

  const handleRescan = useCallback(async () => {
    if (!results[0]?.openclaw_path) {
      setError('No workspace path available')
      return
    }

    // Store scroll position to restore after rescan
    const scrollPosition = window.scrollY

    // Store previous state before rescanning
    previousScanRef.current = {
      topology,
      results,
    }

    setRescanning(true)
    setError(null)

    try {
      const workspacePath = results[0].openclaw_path

      // Trigger new scan
      const trigger = await triggerScan(workspacePath)

      // Poll for completion
      let status = await pollScanStatus(trigger.scan_id)
      while (status.status === 'running') {
        await new Promise(resolve => setTimeout(resolve, 1000))
        status = await pollScanStatus(trigger.scan_id)
      }

      if (status.status === 'failed') {
        throw new Error(status.error || 'Scan failed')
      }

      // Reload data
      const newData = await fetchLatestScan()
      setScanId(newData.scan_id)
      setResults(newData.results)
      setTopology(newData.topology ?? null)

      // Compute diff
      const diff = computeScanDiff(
        previousScanRef.current.topology,
        newData.topology ?? null,
        previousScanRef.current.results,
        newData.results
      )

      if (diff.hasChanges) {
        setScanDiff(diff)

        // Extract new node IDs for glow effect
        const newIds = new Set(
          diff.nodeChanges.filter(c => c.type === 'added').map(c => c.nodeId)
        )
        setNewNodeIds(newIds)

        // Clear glow after 3 seconds
        setTimeout(() => setNewNodeIds(new Set()), 3000)
      }

      // Restore scroll position
      setTimeout(() => window.scrollTo(0, scrollPosition), 0)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rescan failed')
      // Restore scroll position even on error
      setTimeout(() => window.scrollTo(0, scrollPosition), 0)
    } finally {
      setRescanning(false)
    }
  }, [results, topology])

  useEffect(() => { loadData() }, [loadData])

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

      {error && <ErrorBanner error={error} onRetry={loadData} />}

      {loading ? (
        <>
          <div className="loading-skeleton" style={{ height: 320, marginBottom: 'var(--space-6)' }} />
          <div className="findings-grid" style={{ marginTop: 'var(--space-5)' }}>
            {[...Array(6)].map((_, i) => (
              <div key={i} className="loading-skeleton" style={{ height: 132 }} />
            ))}
          </div>
        </>
      ) : results.length === 0 ? (
        <EmptyState
          title="No Scan Results Yet"
          hint="Run an OpenClaw security scan to see compliance findings here."
          icon={
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          }
        />
      ) : (
        <>
          {topology && topology.nodes.length > 0 && (
            <div className="scan-topology-panel" ref={topologyRef}>
              <div className="scan-topology-header">
                <span>Architecture Risk View</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <button
                    className={`phase-toggle${showSkills ? ' active' : ''}`}
                    onClick={() => setShowSkills(prev => !prev)}
                    aria-pressed={showSkills}
                    style={{ padding: '4px 10px' }}
                  >
                    {showSkills ? 'Hide Skills' : 'Show Skills'}
                  </button>
                  <span>{filteredTopology?.nodes.length ?? 0} nodes · {filteredTopology?.edges.length ?? 0} edges</span>
                </div>
              </div>
              <ScanTopologyCanvas
                topology={filteredTopology!}
                onNodeClick={(n) => { setHighlightNode(n ?? null); setPanelNode(n ?? null) }}
                selectedNodeId={highlightNode?.id ?? null}
                newNodeIds={newNodeIds}
              />
            </div>
          )}

          <FindingsSection
            results={results}
            topology={topology}
            workspacePath={meta?.openclaw_path ?? ''}
            onRescan={handleRescan}
            rescanning={rescanning}
            onSelectNode={setHighlightNode}
            onScrollToTopology={scrollToTopology}
            onFixApplied={() => loadData()}
          />
        </>
      )}
      <ScanNodePanel node={panelNode} onClose={() => setPanelNode(null)} />
      <ScanChangesNotification diff={scanDiff} onClose={() => setScanDiff(null)} />
    </div>
  )
}
