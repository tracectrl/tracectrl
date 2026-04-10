import { ENGINE_URL } from './config'

export interface AgentSummary {
  agent_id: string
  name: string
  framework: string
  role: string
  model: string
  tools_observed: string[]
  system_prompt_hash: string
  run_count: number
  observation_count: number
  maturity: string
  first_seen: string
  last_seen: string
}

export interface AgentTool {
  tool_name: string
  tool_category: string
  call_count: number
  error_count: number
  first_seen: string
  last_seen: string
}

export async function fetchAgentList(service?: string | null): Promise<AgentSummary[]> {
  const params = service ? `?service=${encodeURIComponent(service)}` : ''
  const res = await fetch(`${ENGINE_URL}/api/v1/agents${params}`)
  if (!res.ok) throw new Error(`Failed to fetch agents: ${res.statusText}`)
  return res.json()
}

export async function fetchAgentTools(agentId: string): Promise<AgentTool[]> {
  const res = await fetch(`${ENGINE_URL}/api/v1/agents/${encodeURIComponent(agentId)}/tools`)
  if (!res.ok) throw new Error(`Failed to fetch agent tools: ${res.statusText}`)
  return res.json()
}
