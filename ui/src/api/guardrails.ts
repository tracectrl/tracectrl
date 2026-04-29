import { ENGINE_URL } from './config'

export type GuardrailSeverity = 'low' | 'medium' | 'high' | 'critical'
export type GuardrailMode = 'monitoring' | 'blocking'
export type GuardrailTiming = 'post_output' | 'pre_input'
export type GuardrailHealth = 'active' | 'error' | 'disabled'

export interface GuardrailRegistration {
  agent_id: string
  guardrail_name: string
  severity: GuardrailSeverity
  mode: GuardrailMode
  timing: GuardrailTiming
  judge_model: string
  description: string
  health: GuardrailHealth
  health_reason: string
  registered_at: string
  last_seen_at: string
  recent_activity_24h: number
}

export async function fetchGuardrails(agentId?: string): Promise<GuardrailRegistration[]> {
  const params = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : ''
  const res = await fetch(`${ENGINE_URL}/api/v1/guardrails${params}`)
  if (!res.ok) throw new Error(`Failed to fetch guardrails: ${res.statusText}`)
  return res.json()
}

export async function fetchAgentGuardrails(agentId: string): Promise<GuardrailRegistration[]> {
  const res = await fetch(`${ENGINE_URL}/api/v1/agents/${encodeURIComponent(agentId)}/guardrails`)
  if (!res.ok) throw new Error(`Failed to fetch agent guardrails: ${res.statusText}`)
  return res.json()
}
