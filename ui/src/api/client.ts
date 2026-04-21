import { ENGINE_URL } from './config'

export interface TopologyNode {
  id: string
  type: 'agent' | 'tool' | 'skill'
  label: string
  metadata: Record<string, unknown>
}

export interface TopologyEdge {
  id: string
  source: string
  target: string
  type: string
  channel?: string
  observation_count?: number
  call_count?: number
  confidence?: string
  tool_category?: string
}

export interface TopologyGraph {
  nodes: TopologyNode[]
  edges: TopologyEdge[]
}

export async function fetchTopologyGraph(service?: string | null): Promise<TopologyGraph> {
  const params = service ? `?service=${encodeURIComponent(service)}` : ''
  const res = await fetch(`${ENGINE_URL}/api/v1/topology/graph${params}`)
  if (!res.ok) throw new Error(`Failed to fetch topology: ${res.statusText}`)
  return res.json()
}

export async function fetchAgentDetail(agentId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${ENGINE_URL}/api/v1/topology/agents/${agentId}`)
  if (!res.ok) throw new Error(`Failed to fetch agent: ${res.statusText}`)
  return res.json()
}

export async function fetchAgents(): Promise<Record<string, unknown>[]> {
  const res = await fetch(`${ENGINE_URL}/api/v1/risk/agents`)
  if (!res.ok) throw new Error(`Failed to fetch agents: ${res.statusText}`)
  return res.json()
}

export interface AttackPath {
  path_id: string
  rule_id: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  owasp_tag: string
  title: string
  description: string
  agent_id: string
  path_nodes: string[]
  path_edges: string[]
  risk_score: number
  detected_at: string
}

export interface AttackOverlay {
  compromised_nodes: { node_id: string; severity: string; risk_score: number }[]
  attack_edges: { source: string; target: string; rule_id: string; severity: string }[]
}

export async function fetchAttackPaths(): Promise<AttackPath[]> {
  const res = await fetch(`${ENGINE_URL}/api/v1/attack-graph/paths`)
  if (!res.ok) throw new Error(`Failed to fetch attack paths: ${res.statusText}`)
  const data = await res.json()
  return data.paths
}

export async function fetchAttackOverlay(): Promise<AttackOverlay> {
  const res = await fetch(`${ENGINE_URL}/api/v1/attack-graph/overlay`)
  if (!res.ok) throw new Error(`Failed to fetch attack overlay: ${res.statusText}`)
  return res.json()
}
