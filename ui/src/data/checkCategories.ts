export type TopCategory = 'Security' | 'Operational' | 'Compliance' | 'Compound Risk'

export interface CheckCategory {
  top: TopCategory
  sub: string
  subOrder: number
}

// Mapping per the check ID prefix → sub-category + top-category.
// Keeps the four-tab chrome small while letting sub-categories surface as
// headings inside each tab's grid.
const PREFIX_MAP: Record<string, CheckCategory> = {
  'OC-SEC':      { top: 'Security',      sub: 'Advanced Security',          subOrder: 1 },
  'OC-CRED':     { top: 'Security',      sub: 'Credentials',                subOrder: 2 },
  'OC-TOOL':     { top: 'Security',      sub: 'Tools Authorization',        subOrder: 3 },
  'OC-SKILL':    { top: 'Security',      sub: 'Skills / Plugin Security',   subOrder: 4 },
  'OC-GUARD':    { top: 'Security',      sub: 'Guardrails & Prompt Injection', subOrder: 5 },
  'OC-NET':      { top: 'Security',      sub: 'Network',                    subOrder: 6 },
  'OC-ING':      { top: 'Security',      sub: 'Ingress / Channels',         subOrder: 7 },
  'OC-LAT':      { top: 'Security',      sub: 'Lateral Movement',           subOrder: 8 },
  'OC-FS':       { top: 'Security',      sub: 'Filesystem',                 subOrder: 9 },
  'OC-LLM':      { top: 'Security',      sub: 'LLM Provider',               subOrder: 10 },

  'OC-OPS':      { top: 'Operational',   sub: 'Operational Health',         subOrder: 1 },
  'OC-PERS':     { top: 'Operational',   sub: 'Persistence & Scheduling',   subOrder: 2 },
  'OC-PERF':     { top: 'Operational',   sub: 'Performance',                subOrder: 3 },
  'OC-PLUG':     { top: 'Operational',   sub: 'Plugin Integrity',           subOrder: 4 },

  'OC-COMP':     { top: 'Compliance',    sub: 'Compliance & Data Governance', subOrder: 1 },
  'OC-LOG':      { top: 'Compliance',    sub: 'Audit Logging',              subOrder: 2 },

  'COMPOUND':    { top: 'Compound Risk', sub: 'Compound Risk',              subOrder: 1 },
}

const FALLBACK: CheckCategory = { top: 'Security', sub: 'Other', subOrder: 99 }

export function categorize(checkId: string): CheckCategory {
  const parts = checkId.split('-')
  // OC-SEC-002 → "OC-SEC", COMPOUND-001 → "COMPOUND"
  const key = parts.length >= 3 ? `${parts[0]}-${parts[1]}` : parts[0]
  return PREFIX_MAP[key] ?? FALLBACK
}

export const TOP_ORDER: TopCategory[] = ['Security', 'Operational', 'Compliance', 'Compound Risk']
