import { ScanResult } from '../../api/scan'

interface Props {
  result: ScanResult
  category: string
  autoFixable: boolean
  fixed: boolean
  focused: boolean
  onOpen: () => void
  onFocus: () => void
}

function severityTone(severity: string, passed: boolean): string {
  if (passed) return 'pass'
  const s = severity.toLowerCase()
  if (s === 'critical' || s === 'high' || s === 'medium' || s === 'low') return s
  return 'medium'
}

export default function FindingCard({
  result,
  category,
  autoFixable,
  fixed,
  focused,
  onOpen,
  onFocus,
}: Props) {
  const passed = result.passed === 1
  const tone = fixed ? 'fixed' : severityTone(result.severity, passed)
  const label = fixed ? 'FIXED' : passed ? 'PASS' : result.severity.toUpperCase()

  return (
    <button
      type="button"
      className={`finding-card tone-${tone}${focused ? ' is-focused' : ''}${passed ? ' is-passed' : ''}`}
      onClick={onOpen}
      onFocus={onFocus}
      data-check-id={result.check_id}
    >
      <span className="finding-card-rule" aria-hidden="true" />
      <div className="finding-card-top">
        <span className={`finding-card-pill pill-${tone}`}>{label}</span>
        <span className="finding-card-id">{result.check_id}</span>
      </div>
      <div className="finding-card-title">{result.title}</div>
      <div className="finding-card-meta">
        <span>{category}</span>
        <span className="finding-card-dot">·</span>
        <span>{result.section}</span>
        {autoFixable && !fixed && !passed && (
          <span className="finding-card-autofix">
            <span aria-hidden="true">⚡</span> auto-fix
          </span>
        )}
      </div>
    </button>
  )
}
