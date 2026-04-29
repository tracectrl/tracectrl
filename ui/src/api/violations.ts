import { ENGINE_URL } from './config'

export type Severity = 'critical' | 'high' | 'medium' | 'low'
export type Decision = 'pass' | 'fail' | 'error'

export interface Violation {
  violation_id: string
  trace_id: string
  span_id: string
  eval_span_id: string
  agent_id: string
  guardrail_name: string
  judge_model: string
  decision: Decision
  reason: string
  evidence: string
  severity: Severity
  observed_at: string
}

export async function fetchViolations(opts: { limit?: number; severity?: Severity } = {}): Promise<Violation[]> {
  const params = new URLSearchParams()
  if (opts.limit != null) params.set('limit', String(opts.limit))
  if (opts.severity) params.set('severity', opts.severity)
  const qs = params.toString()
  const res = await fetch(`${ENGINE_URL}/api/v1/violations${qs ? `?${qs}` : ''}`)
  if (!res.ok) throw new Error(`Failed to fetch violations: ${res.statusText}`)
  return res.json()
}

export async function fetchRecentViolations(limit = 20): Promise<Violation[]> {
  const res = await fetch(`${ENGINE_URL}/api/v1/violations/recent?limit=${limit}`)
  if (!res.ok) throw new Error(`Failed to fetch recent violations: ${res.statusText}`)
  return res.json()
}

export function openViolationStream(): EventSource {
  return new EventSource(`${ENGINE_URL}/api/v1/violations/stream`)
}

export const SEVERITY_RANK: Record<Severity, number> = {
  low: 1,
  medium: 2,
  high: 3,
  critical: 4,
}
