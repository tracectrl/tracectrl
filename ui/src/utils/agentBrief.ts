import { ScanResult } from '../api/scan'
import { categorize } from '../data/checkCategories'

const DOCS_ROOT = 'https://docs.openclaw.ai'

interface BuildOptions {
  workspacePath?: string
}

/**
 * Produce a markdown prompt for a coding agent to fix a single finding.
 * Self-contained — can be pasted into Claude / Cursor / Aider.
 */
export function buildSingleBrief(r: ScanResult, opts: BuildOptions = {}): string {
  const cat = categorize(r.check_id)
  const lines = [
    `# Fix TraceCtrl finding ${r.check_id}`,
    '',
    `**Severity:** ${r.severity.toUpperCase()}  `,
    `**Category:** ${cat.top} · ${cat.sub}  `,
    `**Title:** ${r.title}`,
    '',
    '## Evidence',
    r.finding || '(no evidence captured)',
    '',
    '## Fix',
    r.remediation || '(no remediation text supplied; inspect the relevant openclaw.json and apply a secure default)',
    '',
  ]
  if (r.config_path) {
    lines.push('## Source', `\`${r.config_path}\``, '')
  }
  if (opts.workspacePath) {
    lines.push('## Workspace', `\`${opts.workspacePath}\``, '')
  }
  lines.push(
    '## References',
    `- OpenClaw configuration docs: ${DOCS_ROOT}`,
    '',
    '## Task',
    `Please inspect the OpenClaw workspace, apply the fix above, and verify with \`tracectrl scan\`. Do not introduce new findings. Confirm the resulting config passes ${r.check_id}.`,
  )
  return lines.join('\n')
}

/**
 * Produce a single aggregated markdown prompt covering all non-auto-fixable
 * failing findings. Intended for the page-level "Copy Agent Brief" button.
 */
export function buildAggregateBrief(items: ScanResult[], opts: BuildOptions = {}): string {
  if (items.length === 0) return ''

  const header = [
    '# TraceCtrl — manual security fixes',
    '',
    `You are helping fix **${items.length}** TraceCtrl security finding${items.length === 1 ? '' : 's'} that the auto-fixer cannot resolve. Each task below is self-contained.`,
    '',
    opts.workspacePath ? `**Workspace:** \`${opts.workspacePath}\`` : '',
    `**Reference:** ${DOCS_ROOT}`,
    '',
    '## Task list',
    '',
  ].filter(Boolean)

  const tasks = items.map((r, i) => {
    const cat = categorize(r.check_id)
    const parts = [
      `### ${i + 1}. ${r.check_id} — ${r.title}`,
      `_${r.severity.toUpperCase()} · ${cat.top} · ${cat.sub}_`,
      '',
    ]
    if (r.finding) { parts.push('**Evidence:** ' + r.finding, '') }
    parts.push('**Fix:** ' + (r.remediation || '(inspect config and apply a secure default)'))
    if (r.config_path) { parts.push('', '**Source:** `' + r.config_path + '`') }
    return parts.join('\n')
  })

  const footer = [
    '',
    '## Verification',
    'After each fix, run `tracectrl scan` and confirm no new findings were introduced. Report which checks now pass.',
  ]

  return [...header, ...tasks, ...footer].join('\n')
}
