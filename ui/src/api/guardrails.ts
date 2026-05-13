import { ENGINE_URL } from './config'

export type GuardrailSeverity = 'low' | 'medium' | 'high' | 'critical'
export type GuardrailMode = 'monitoring' | 'blocking'
export type GuardrailTiming = 'post_output' | 'pre_input'
export type GuardrailHealth = 'active' | 'error' | 'disabled'
// 'judge_llm' is the legacy in-SDK LLM-judge guardrails; 'protector_plus' is
// the Cloudsine GenAI Protector Plus integration (TraceCtrl Guards).
export type GuardrailProvider = 'judge_llm' | 'protector_plus'

export interface GuardrailRegistration {
  agent_id: string
  guardrail_name: string
  severity: GuardrailSeverity
  mode: GuardrailMode
  timing: GuardrailTiming
  judge_model: string
  description: string
  judge_prompt: string
  health: GuardrailHealth
  health_reason: string
  registered_at: string
  last_seen_at: string
  recent_activity_24h: number
  provider?: GuardrailProvider
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

export type GuardrailDecision = 'pass' | 'fail' | 'error'

export interface GuardrailInvocation {
  trace_id: string
  span_id: string
  observed_at: string
  decision: GuardrailDecision
  timing: GuardrailTiming | ''
  reason: string
  evidence: string
  severity: GuardrailSeverity
  provider: GuardrailProvider
  judge_model: string
  // Protector Plus only — empty string for legacy judge_llm spans.
  response_json: string
}

export async function fetchGuardrailInvocations(
  agentId: string,
  guardrailName: string,
  limit = 50,
): Promise<GuardrailInvocation[]> {
  const params = new URLSearchParams({
    agent_id: agentId,
    guardrail_name: guardrailName,
    limit: String(limit),
  })
  const res = await fetch(`${ENGINE_URL}/api/v1/guardrails/invocations?${params.toString()}`)
  if (!res.ok) throw new Error(`Failed to fetch invocations: ${res.statusText}`)
  return res.json()
}
