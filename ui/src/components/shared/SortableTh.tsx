import { ReactNode } from 'react'

type Dir = 'asc' | 'desc' | null

interface Props {
  children: ReactNode
  active: boolean
  direction: Dir
  onToggle: () => void
  style?: React.CSSProperties
}

export default function SortableTh({ children, active, direction, onToggle, style }: Props) {
  const ariaSort = active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'
  return (
    <th aria-sort={ariaSort} style={style}>
      <button
        type="button"
        className={`th-sort${active ? ' is-active' : ''}`}
        onClick={onToggle}
      >
        <span className="th-sort-label">{children}</span>
        <span className="th-sort-arrow" aria-hidden="true">
          {active ? (direction === 'asc' ? '↑' : '↓') : '↕'}
        </span>
      </button>
    </th>
  )
}
