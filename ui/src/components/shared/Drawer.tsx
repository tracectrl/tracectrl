import { ReactNode, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'

type Tone = 'critical' | 'high' | 'medium' | 'low' | 'pass' | 'fixed' | 'neutral'

type Placement = 'right' | 'bottom'

interface Props {
  open: boolean
  onClose: () => void
  ariaLabel: string
  children: ReactNode
  widthPx?: number
  heightPx?: number
  tone?: Tone
  placement?: Placement
}

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

export default function Drawer({
  open,
  onClose,
  ariaLabel,
  children,
  widthPx = 480,
  heightPx = 460,
  tone = 'neutral',
  placement = 'right',
}: Props) {
  const drawerRef = useRef<HTMLElement>(null)
  const returnFocusRef = useRef<HTMLElement | null>(null)

  // Esc to close
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  // Focus management + Tab trap
  useEffect(() => {
    if (!open) return
    returnFocusRef.current = document.activeElement as HTMLElement | null

    const t = window.setTimeout(() => {
      const firstBtn = drawerRef.current?.querySelector<HTMLElement>('button, [tabindex="0"]')
      firstBtn?.focus()
    }, 60)

    const onTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !drawerRef.current) return
      const nodes = Array.from(drawerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE))
        .filter(n => !n.hasAttribute('disabled') && n.offsetParent !== null)
      if (nodes.length === 0) { e.preventDefault(); return }
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      const active = document.activeElement as HTMLElement | null
      if (e.shiftKey && active === first) { last.focus(); e.preventDefault() }
      else if (!e.shiftKey && active === last) { first.focus(); e.preventDefault() }
      else if (active && !drawerRef.current.contains(active)) { first.focus(); e.preventDefault() }
    }
    window.addEventListener('keydown', onTab, true)

    return () => {
      window.clearTimeout(t)
      window.removeEventListener('keydown', onTab, true)
      returnFocusRef.current?.focus?.()
    }
  }, [open])

  // Lock body scroll
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = prev }
  }, [open])

  if (!open && !drawerRef.current) return null

  return createPortal(
    <div
      className={`drawer-root drawer-root--${placement}${open ? ' is-open' : ''}`}
      aria-hidden={!open}
    >
      <div className="drawer-backdrop" onClick={onClose} />
      <aside
        ref={drawerRef}
        className={`drawer drawer--${placement} tone-${tone}`}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        style={placement === 'bottom' ? { height: heightPx } : { width: widthPx }}
      >
        {children}
      </aside>
    </div>,
    document.body
  )
}

export function DrawerClose({ onClose }: { onClose: () => void }) {
  return (
    <button
      type="button"
      className="drawer-close"
      onClick={onClose}
      aria-label="Close"
      title="Close (Esc)"
    >
      ×
    </button>
  )
}
