import { useEffect, useMemo, useState } from 'react'
import { ScanResult } from '../../api/scan'
import Drawer, { DrawerClose } from '../shared/Drawer'
import { buildAggregateBrief } from '../../utils/agentBrief'

interface Props {
  open: boolean
  onClose: () => void
  findings: ScanResult[]
  workspacePath?: string
}

export default function AgentBriefDrawer({ open, onClose, findings, workspacePath }: Props) {
  const [copied, setCopied] = useState(false)

  const markdown = useMemo(
    () => buildAggregateBrief(findings, { workspacePath }),
    [findings, workspacePath]
  )

  useEffect(() => { if (!open) setCopied(false) }, [open])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(markdown)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2200)
    } catch {
      /* clipboard unavailable (non-HTTPS context) */
    }
  }

  return (
    <Drawer
      open={open}
      onClose={onClose}
      ariaLabel="Agent brief preview"
      tone="neutral"
      widthPx={640}
    >
      <header className="drawer-header">
        <div>
          <div className="drawer-crumb"><span>Agent brief</span></div>
          <h3 className="drawer-title" style={{ margin: 0 }}>
            {findings.length} finding{findings.length === 1 ? '' : 's'} · ready for your agent
          </h3>
        </div>
        <div style={{ marginLeft: 'auto' }}>
          <DrawerClose onClose={onClose} />
        </div>
      </header>

      <div className="drawer-body">
        <p className="agent-brief-intro">
          Paste this into Claude, Cursor, Aider, or any coding agent with access to your OpenClaw workspace. Each entry links to the relevant docs page so the agent can research the exact fix before applying it.
        </p>
        <pre className="agent-brief-preview">{markdown}</pre>
      </div>

      <footer className="drawer-footer">
        <span className="agent-brief-length">{markdown.length.toLocaleString()} chars</span>
        <div style={{ flex: 1 }} />
        <button className="btn btn-ghost btn-sm" onClick={onClose}>Close</button>
        <button
          className="btn btn-primary btn-sm"
          onClick={handleCopy}
          disabled={findings.length === 0}
        >
          {copied ? '✓ Copied' : 'Copy brief'}
        </button>
      </footer>
    </Drawer>
  )
}
