const ENGINE_URL = import.meta.env.VITE_ENGINE_URL || 'http://localhost:8000'

export interface TopologyNode {
  id: string
  type: 'agent' | 'tool'
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

export async function fetchTopologyGraph(): Promise<TopologyGraph> {
  const res = await fetch(`${ENGINE_URL}/api/v1/topology/graph`)
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
