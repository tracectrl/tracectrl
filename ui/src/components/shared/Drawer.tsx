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

    // Focus the drawer container itself instead of the first button. Focusing
    // the close `×` button immediately on open is jarring (the visual focus
    // ring jumps to the far corner) and makes Tab navigation feel reversed.
    // The container has tabIndex=-1 set inline below so it's programmatically
    // focusable but not in the tab cycle.
    const t = window.setTimeout(() => {
      drawerRef.current?.focus()
    }, 60)

    // Soft focus management for non-modal drawers: only loop within the drawer
    // when focus is already inside it. Don't fight a user who tabs out into
    // the sidebar / page — that's intentional in inspector-pane mode.
    const onTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !drawerRef.current) return
      const active = document.activeElement as HTMLElement | null
      if (!active || !drawerRef.current.contains(active)) return
      const nodes = Array.from(drawerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE))
        .filter(n => !n.hasAttribute('disabled') && n.offsetParent !== null)
      if (nodes.length === 0) return
      const first = nodes[0]
      const last = nodes[nodes.length - 1]
      if (e.shiftKey && active === first) { last.focus(); e.preventDefault() }
      else if (!e.shiftKey && active === last) { first.focus(); e.preventDefault() }
    }
    window.addEventListener('keydown', onTab, true)

    return () => {
      window.clearTimeout(t)
      window.removeEventListener('keydown', onTab, true)
      returnFocusRef.current?.focus?.()
    }
  }, [open])

  // Drawers are inspector panes, not modals — the rest of the page stays
  // scrollable and interactive. No body-scroll lock.

  // Publish a CSS variable so the toast container can shift left by the
  // drawer's width when a right-placed drawer is open (otherwise toasts
  // overlap the drawer's close button).
  useEffect(() => {
    if (!open || placement !== 'right') return
    const offsetPx = `${widthPx + 16}px`
    const prev = document.body.style.getPropertyValue('--right-drawer-offset')
    document.body.style.setProperty('--right-drawer-offset', offsetPx)
    return () => {
      if (prev) document.body.style.setProperty('--right-drawer-offset', prev)
      else document.body.style.removeProperty('--right-drawer-offset')
    }
  }, [open, placement, widthPx])

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
        aria-modal="false"
        aria-label={ariaLabel}
        tabIndex={-1}
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
