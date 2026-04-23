import { ReactNode } from 'react'

interface Props {
  icon?: ReactNode
  title: string
  hint?: string
  action?: ReactNode
}

const DEFAULT_ICON = (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="10" />
    <path d="M12 8v4M12 16h.01" />
  </svg>
)

export default function EmptyState({ icon, title, hint, action }: Props) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">{icon ?? DEFAULT_ICON}</div>
      <h3>{title}</h3>
      {hint && <p>{hint}</p>}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  )
}
