const ENGINE_URL = import.meta.env.VITE_ENGINE_URL || 'http://localhost:8000'

export interface SessionSummary {
  trace_id: string
  start_time: string
  end_time: string
  total_duration_ns: number
  span_count: number
  root_span_name: string
  root_span_id: string
  agent_name: string
  has_error: boolean
}

export interface SpanDetail {
  span_id: string
  parent_span_id: string
  span_name: string
  span_kind: string
  service_name: string
  start_ns: number
  duration_ns: number
  status_code: string
  status_message: string
  attributes: Record<string, string>
  resource_attributes: Record<string, string>
}

export function formatDuration(ns: number): string {
  if (ns < 1_000) return `${ns}ns`
  if (ns < 1_000_000) return `${(ns / 1_000).toFixed(1)}µs`
  if (ns < 1_000_000_000) return `${(ns / 1_000_000).toFixed(1)}ms`
  return `${(ns / 1_000_000_000).toFixed(2)}s`
}

export async function fetchSessions(): Promise<SessionSummary[]> {
  const res = await fetch(`${ENGINE_URL}/api/v1/sessions`)
  if (!res.ok) throw new Error(`Failed to fetch sessions: ${res.statusText}`)
  return res.json()
}

export async function fetchTraceSpans(traceId: string): Promise<SpanDetail[]> {
  const res = await fetch(`${ENGINE_URL}/api/v1/sessions/${traceId}/spans`)
  if (!res.ok) throw new Error(`Failed to fetch spans: ${res.statusText}`)
  return res.json()
}
