import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { ScanResult } from '../../api/scan'
import ConfigCodeBlock from '../ConfigCodeBlock'

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

function severityTone(severity: string, passed: boolean): string {
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
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose() }
      else if (e.key === 'ArrowDown' || e.key === 'j') { onNext?.(); e.preventDefault() }
      else if (e.key === 'ArrowUp' || e.key === 'k') { onPrev?.(); e.preventDefault() }
    }
    window.addEventListener('keydown', onKey)
    // focus the close button for a11y (keeps Tab focus contained-ish without a full trap)
    const t = window.setTimeout(() => closeRef.current?.focus(), 60)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.clearTimeout(t)
    }
  }, [open, onClose, onNext, onPrev])

  // Lock body scroll while drawer is open
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [open])

  if (!result) return null

  const passed = result.passed === 1
  const tone = fixed ? 'fixed' : severityTone(result.severity, passed)
  const label = fixed ? 'FIXED' : passed ? 'PASS' : result.severity.toUpperCase()

  const body = (
    <div className={`finding-drawer-root${open ? ' is-open' : ''}`} aria-hidden={!open}>
      <div className="finding-drawer-backdrop" onClick={onClose} />
      <aside
        className={`finding-drawer tone-${tone}`}
        role="dialog"
        aria-modal="true"
        aria-label={`${result.check_id}: ${result.title}`}
      >
        <header className="finding-drawer-top">
          <span className={`finding-card-pill pill-${tone}`}>{label}</span>
          <span className="finding-drawer-id">{result.check_id}</span>
          <div className="finding-drawer-nav">
            {onPrev && (
              <button className="finding-drawer-navbtn" onClick={onPrev} aria-label="Previous finding" title="Previous (↑ or k)">
                ↑
              </button>
            )}
            {onNext && (
              <button className="finding-drawer-navbtn" onClick={onNext} aria-label="Next finding" title="Next (↓ or j)">
                ↓
              </button>
            )}
            <button
              ref={closeRef}
              className="finding-drawer-close"
              onClick={onClose}
              aria-label="Close"
              title="Close (Esc)"
            >
              ×
            </button>
          </div>
        </header>

        <div className="finding-drawer-scroll">
          <div className="finding-drawer-crumb">
            <span>{category}</span>
            <span aria-hidden="true">›</span>
            <span>{result.section}</span>
          </div>

          <h3 className="finding-drawer-title">{result.title}</h3>

          {result.finding && (
            <div className={`finding-drawer-verdict verdict-${tone}`}>
              <p>{result.finding}</p>
            </div>
          )}

          {result.remediation && (
            <section className="finding-drawer-section">
              <h4 className="finding-drawer-h">Remediation</h4>
              <p className="finding-drawer-body">{result.remediation}</p>
            </section>
          )}

          <section className="finding-drawer-section">
            <h4 className="finding-drawer-h">Config snippet</h4>
            <ConfigCodeBlock checkId={result.check_id} />
          </section>

          {result.config_path && (
            <section className="finding-drawer-section">
              <h4 className="finding-drawer-h">Source</h4>
              <code className="finding-drawer-path">{result.config_path}</code>
            </section>
          )}
        </div>

        <footer className="finding-drawer-foot">
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
      </aside>
    </div>
  )

  return createPortal(body, document.body)
}
