const ENGINE_URL = import.meta.env.VITE_ENGINE_URL || 'http://localhost:8000'

export interface AttackPathStep {
  node_id: string
  node_type: string
  vulnerability: string
  description: string
}

export interface AttackPath {
  path_id: string
  rule_name: string
  owasp_category: string
  agents_involved: string[]
  path_steps: AttackPathStep[]
  risk_score: number
  severity: string
  computed_at: string
}

export interface AgentRisk {
  agent_id: string
  risk_score: number
  severity: string
  path_count: number
  top_rule: string
  computed_at: string
}

export interface RiskSummary {
  risk_score: number
  severity: string
  critical_paths: number
  agents_at_risk: number
  learning_agents: number
  computed_at: string
}

export async function fetchRiskSummary(): Promise<RiskSummary | null> {
  const res = await fetch(`${ENGINE_URL}/api/v1/risk/summary`)
  if (!res.ok) throw new Error(`Failed to fetch risk summary: ${res.statusText}`)
  return res.json()
}

export async function fetchAttackPaths(service?: string | null): Promise<AttackPath[]> {
  const params = service ? `?service=${encodeURIComponent(service)}` : ''
  const res = await fetch(`${ENGINE_URL}/api/v1/risk/attack-paths${params}`)
  if (!res.ok) throw new Error(`Failed to fetch attack paths: ${res.statusText}`)
  return res.json()
}

export async function fetchAgentRisks(service?: string | null): Promise<AgentRisk[]> {
  const params = service ? `?service=${encodeURIComponent(service)}` : ''
  const res = await fetch(`${ENGINE_URL}/api/v1/risk/agent-scores${params}`)
  if (!res.ok) throw new Error(`Failed to fetch agent risks: ${res.statusText}`)
  return res.json()
}

export function severityBadgeClass(severity: string): string {
  switch (severity.toLowerCase()) {
    case 'critical': return 'badge-critical'
    case 'high': return 'badge-high'
    case 'medium': return 'badge-medium'
    default: return 'badge-low'
  }
}

export function severityColor(severity: string): string {
  switch (severity.toLowerCase()) {
    case 'critical': return 'var(--risk-critical)'
    case 'high': return 'var(--risk-high)'
    case 'medium': return 'var(--risk-medium)'
    default: return 'var(--risk-low)'
  }
}
