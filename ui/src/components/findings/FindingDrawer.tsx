import { useEffect } from 'react'
import { ScanResult } from '../../api/scan'
import ConfigCodeBlock from '../ConfigCodeBlock'
import Drawer, { DrawerClose } from '../shared/Drawer'

interface Props {
  result: ScanResult | null
  category: string
  autoFixable: boolean
  fixed: boolean
  fixing: boolean
  open: boolean
  onClose: () => void
  onFix: (checkId: string) => void
  onPrev?: () => void
  onNext?: () => void
}

function severityTone(severity: string, passed: boolean): 'critical' | 'high' | 'medium' | 'low' | 'pass' {
  if (passed) return 'pass'
  const s = severity.toLowerCase()
  if (s === 'critical' || s === 'high' || s === 'medium' || s === 'low') return s
  return 'medium'
}

export default function FindingDrawer({
  result,
  category,
  autoFixable,
  fixed,
  fixing,
  open,
  onClose,
  onFix,
  onPrev,
  onNext,
}: Props) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown' || e.key === 'j') { onNext?.(); e.preventDefault() }
      else if (e.key === 'ArrowUp' || e.key === 'k') { onPrev?.(); e.preventDefault() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onNext, onPrev])

  if (!result) return null

  const passed = result.passed === 1
  const tone = fixed ? 'fixed' : severityTone(result.severity, passed)
  const label = fixed ? 'FIXED' : passed ? 'PASS' : result.severity.toUpperCase()

  return (
    <Drawer
      open={open}
      onClose={onClose}
      ariaLabel={`${result.check_id}: ${result.title}`}
      tone={tone}
      widthPx={480}
    >
      <header className="drawer-header">
        <span className={`finding-card-pill pill-${tone}`}>{label}</span>
        <span className="finding-drawer-id">{result.check_id}</span>
        <div className="finding-drawer-nav">
          {onPrev && (
            <button className="drawer-navbtn" onClick={onPrev} aria-label="Previous finding" title="Previous (↑ or k)">↑</button>
          )}
          {onNext && (
            <button className="drawer-navbtn" onClick={onNext} aria-label="Next finding" title="Next (↓ or j)">↓</button>
          )}
          <DrawerClose onClose={onClose} />
        </div>
      </header>

      <div className="drawer-body">
        <div className="drawer-crumb">
          <span>{category}</span>
          <span aria-hidden="true">›</span>
          <span>{result.section}</span>
        </div>

        <h3 className="drawer-title">{result.title}</h3>

        {result.finding && (
          <div className={`finding-drawer-verdict verdict-${tone}`}>
            <p>{result.finding}</p>
          </div>
        )}

        {result.remediation && (
          <section className="drawer-section">
            <h4 className="drawer-h">Remediation</h4>
            <p>{result.remediation}</p>
          </section>
        )}

        <section className="drawer-section">
          <h4 className="drawer-h">Config snippet</h4>
          <ConfigCodeBlock checkId={result.check_id} />
        </section>

        {result.config_path && (
          <section className="drawer-section">
            <h4 className="drawer-h">Source</h4>
            <code className="drawer-mono-path">{result.config_path}</code>
          </section>
        )}

      </div>

      <footer className="drawer-footer">
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => navigator.clipboard?.writeText(result.check_id)}
        >
          Copy ID
        </button>
        <div style={{ flex: 1 }} />
        {autoFixable && !fixed && !passed && (
          <button
            className="btn btn-primary btn-sm"
            onClick={() => onFix(result.check_id)}
            disabled={fixing}
          >
            {fixing ? 'Fixing…' : 'Fix this'}
          </button>
        )}
      </footer>
    </Drawer>
  )
}
