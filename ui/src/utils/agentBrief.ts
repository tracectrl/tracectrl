import { ScanResult } from '../api/scan'
import { categorize } from '../data/checkCategories'
import { AGENT_BRIEFS, AgentBrief } from '../data/agentBriefs'

const DOCS_ROOT = 'https://docs.openclaw.ai'

interface BuildOptions {
  workspacePath?: string
}

function briefFor(checkId: string): AgentBrief | null {
  return AGENT_BRIEFS[checkId] ?? null
}

/**
 * Aggregate markdown for ALL non-auto-fixable findings passed in.
 * Format: short header explaining the task, then per-finding blocks
 * with problem / location / docs link / optional hint / raw evidence.
 * The agent is expected to visit each docs link and apply the fix.
 */
export function buildAggregateBrief(items: ScanResult[], opts: BuildOptions = {}): string {
  if (items.length === 0) return ''

  const header: string[] = [
    '# TraceCtrl — manual security fixes',
    '',
    `You are helping fix **${items.length}** OpenClaw security finding${items.length === 1 ? '' : 's'} that the TraceCtrl auto-fixer cannot resolve.`,
    '',
    'For each item below:',
    '1. Read the linked docs page to understand the configuration.',
    '2. Open the indicated file / JSON path.',
    '3. Apply the minimal fix that resolves the finding without relaxing other controls.',
    '4. After each change, run `tracectrl scan` and confirm no new findings were introduced.',
    '',
  ]
  if (opts.workspacePath) header.push(`**Workspace:** \`${opts.workspacePath}\``, '')
  header.push(`**Docs root:** ${DOCS_ROOT}`, '', '---', '')

  const tasks = items.map((r, i) => {
    const cat = categorize(r.check_id)
    const hand = briefFor(r.check_id)
    const lines: string[] = [
      `## ${i + 1}. ${r.check_id} — ${r.title}`,
      `_${r.severity.toUpperCase()} · ${cat.top} · ${cat.sub}_`,
      '',
    ]

    if (hand) {
      lines.push(`**Problem:** ${hand.problem}`)
      lines.push(`**Location:** ${hand.location}`)
      lines.push(`**Docs:** ${hand.docsUrl}`)
      if (hand.hint) lines.push(`**Hint:** ${hand.hint}`)
    } else {
      // Fallback: use scanner-supplied remediation + generic docs root.
      if (r.finding) lines.push(`**Problem:** ${r.finding}`)
      if (r.remediation) lines.push(`**Hint:** ${r.remediation}`)
      lines.push(`**Docs:** ${DOCS_ROOT}`)
    }

    if (r.finding && hand) {
      lines.push('', `> Scanner evidence: ${r.finding}`)
    }
    if (r.config_path) lines.push('', `**Source:** \`${r.config_path}\``)
    return lines.join('\n')
  })

  const footer = [
    '',
    '---',
    '',
    '## Verification',
    'Once all items are addressed, run `tracectrl scan` and report which findings now pass.',
  ]

  return [...header, ...tasks, ...footer].join('\n')
}

// Still exported for parity — per-finding brief reuses the aggregate formatter
// with a one-item list so single and bulk output stay structurally identical.
export function buildSingleBrief(r: ScanResult, opts: BuildOptions = {}): string {
  return buildAggregateBrief([r], opts)
}
