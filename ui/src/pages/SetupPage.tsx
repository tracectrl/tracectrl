import { useState, useEffect, useRef } from 'react'
import { validateWorkspacePath, triggerScan, pollScanStatus, fetchLatestScan, ScanDetail } from '../api/scan'
import FindingsSection from '../components/findings/FindingsSection'

type FlowState = 'path_entry' | 'validating' | 'scanning' | 'results'

const MAX_POLL_ERRORS = 3

export default function SetupPage() {
  useEffect(() => { document.title = 'Setup — TraceCtrl' }, [])

  const [state, setState] = useState<FlowState>('path_entry')
  const [path, setPath] = useState('')
  const [pathError, setPathError] = useState<string | null>(null)
  const [activeScanId, setActiveScanId] = useState<string | null>(null)
  const [scanError, setScanError] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [scanData, setScanData] = useState<ScanDetail | null>(null)
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollErrorCount = useRef(0)

  useEffect(() => {
    if (state === 'scanning') {
      setElapsed(0)
      elapsedRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    } else {
      if (elapsedRef.current) clearInterval(elapsedRef.current)
    }
    return () => { if (elapsedRef.current) clearInterval(elapsedRef.current) }
  }, [state])

  useEffect(() => {
    if (state !== 'scanning' || !activeScanId) return
    pollErrorCount.current = 0
    const poll = setInterval(async () => {
      try {
        const status = await pollScanStatus(activeScanId)
        pollErrorCount.current = 0
        if (status.status === 'complete') {
          clearInterval(poll)
          const data = await fetchLatestScan()
          setScanData(data)
          setState('results')
        } else if (status.status === 'failed') {
          clearInterval(poll)
          setScanError(status.error || 'Scan failed')
          setState('path_entry')
        }
      } catch (e) {
        pollErrorCount.current += 1
        if (pollErrorCount.current >= MAX_POLL_ERRORS) {
          clearInterval(poll)
          setScanError(e instanceof Error ? e.message : 'Lost connection to engine — check that the TraceCtrl engine is running')
          setState('path_entry')
        }
      }
    }, 2000)
    return () => clearInterval(poll)
  }, [state, activeScanId])

  const handleScanNow = async () => {
    if (!path.trim()) { setPathError('Enter your OpenClaw workspace path'); return }
    setPathError(null)
    setState('validating')
    try {
      const v = await validateWorkspacePath(path.trim())
      if (!v.valid) { setPathError(v.error || 'Path not found'); setState('path_entry'); return }
      if (!v.openclaw_json_found) { setPathError('openclaw.json not found in this directory'); setState('path_entry'); return }
      const trigger = await triggerScan(path.trim())
      setActiveScanId(trigger.scan_id)
      setState('scanning')
    } catch (e: unknown) {
      setPathError(e instanceof Error ? e.message : 'Failed to start scan')
      setState('path_entry')
    }
  }

  const handleRescan = async () => {
    if (!path.trim()) return
    setScanError(null)
    setState('validating')
    try {
      const trigger = await triggerScan(path.trim())
      setActiveScanId(trigger.scan_id)
      setState('scanning')
    } catch (e: unknown) {
      setScanError(e instanceof Error ? e.message : 'Failed to start rescan')
      setState('results')
    }
  }

  return (
    <div>
      <div className="page-header">
        <div className="section-tag">Security</div>
        <h2>Setup &amp; First Scan</h2>
        <p className="page-meta">Run your first security scan against your OpenClaw workspace.</p>
      </div>

      {(state === 'path_entry' || state === 'validating') && (
        <div className="setup-card">
          <div className="setup-card-body">
            <label className="setup-label" htmlFor="workspace-path">
              OpenClaw workspace path
            </label>
            <p className="setup-hint">
              Run <code>openclaw configure</code> in your terminal &mdash; the first line of output is your workspace path.
            </p>
            <div className="setup-input-row">
              <input
                id="workspace-path"
                className="setup-input"
                type="text"
                placeholder="/home/user/.openclaw"
                value={path}
                onChange={e => setPath(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleScanNow()}
                disabled={state === 'validating'}
                aria-describedby={pathError ? 'path-error' : undefined}
              />
              <button
                className="btn btn-primary"
                onClick={handleScanNow}
                disabled={state === 'validating'}
              >
                {state === 'validating' ? 'Validating…' : 'Scan Now'}
              </button>
            </div>
            {pathError && (
              <p id="path-error" className="setup-error">{pathError}</p>
            )}
          </div>
        </div>
      )}

      {state === 'scanning' && (
        <div className="setup-card">
          <div className="setup-scanning-body">
            <div className="setup-spinner" aria-label="Scanning" />
            <div>
              <p className="setup-scanning-label">Scanning workspace&hellip;</p>
              <p className="setup-scanning-meta">{elapsed}s elapsed &middot; Running 38 security checks</p>
            </div>
          </div>
        </div>
      )}

      {state === 'results' && scanData && (
        <>
          {scanError && <div className="error-banner" role="alert">{scanError}</div>}
          <FindingsSection
            results={scanData.results}
            topology={scanData.topology ?? null}
            workspacePath={path}
            onRescan={handleRescan}
            onSelectNode={() => {}}
            onScrollToTopology={() => {}}
            onFixApplied={() => handleRescan()}
          />
        </>
      )}
    </div>
  )
}
