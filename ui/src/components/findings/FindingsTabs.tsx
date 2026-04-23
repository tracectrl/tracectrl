import { useMemo } from 'react'

export interface TabStat {
  key: string
  label: string
  total: number
  failed: number
}

interface Props {
  tabs: TabStat[]
  active: string
  onChange: (key: string) => void
}

export default function FindingsTabs({ tabs, active, onChange }: Props) {
  const enriched = useMemo(
    () =>
      tabs.map(t => ({
        ...t,
        passed: Math.max(0, t.total - t.failed),
        ratio: t.total === 0 ? 1 : Math.max(0, t.total - t.failed) / t.total,
      })),
    [tabs]
  )

  return (
    <div className="findings-tabs" role="tablist" aria-label="Finding categories">
      {enriched.map(t => {
        const isActive = t.key === active
        return (
          <button
            key={t.key}
            role="tab"
            aria-selected={isActive}
            className={`findings-tab${isActive ? ' is-active' : ''}${t.failed > 0 ? ' has-failures' : ''}`}
            onClick={() => onChange(t.key)}
          >
            <span className="findings-tab-label">{t.label}</span>
            <span className="findings-tab-count">
              {t.total === 0 ? '0' : t.failed > 0 ? `${t.failed} open` : `${t.total} clean`}
            </span>
            <span className="findings-tab-track" aria-hidden="true">
              <span
                className="findings-tab-fill"
                style={{ width: `${Math.round(t.ratio * 100)}%` }}
              />
            </span>
          </button>
        )
      })}
    </div>
  )
}
