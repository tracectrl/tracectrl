import { ENGINE_URL } from './config'

export interface ProtectorConfig {
  endpoint_url: string
  api_key: string
  enabled_guardrails: string[]
  updated_at?: string | null
}

export interface ProtectorTestResult {
  ok: boolean
  ms: number
  status_code?: number | null
  error?: string | null
}

// The 7 Protector Plus guardrails. Keys must match what the engine accepts.
// Order is the canonical display order in the Settings UI.
export const PROTECTOR_GUARDRAILS: { key: string; label: string; description: string }[] = [
  {
    key: 'llm',
    label: 'LLM Judge',
    description: 'Scores prompt injection likelihood 0–1 via an LLM judge (llama4:scout).',
  },
  {
    key: 'pii',
    label: 'PII Detection',
    description: 'Detects names, emails, phone numbers, IC/passport, credit cards via NER.',
  },
  {
    key: 'content_moderation',
    label: 'Content Moderation',
    description: 'Classifies harmful content via Qwen3Guard-4B.',
  },
  {
    key: 'vector',
    label: 'Vector Similarity',
    description: 'Semantic similarity to known injection patterns (bge-m3 + ChromaDB).',
  },
  {
    key: 'system_prompt_protection',
    label: 'System Prompt Protection',
    description: 'Detects when the LLM is leaking its system prompt in its response.',
  },
  {
    key: 'keyword',
    label: 'Keyword',
    description: 'Exact keyword/phrase blocklist match.',
  },
  {
    key: 'regex',
    label: 'Regex',
    description: 'Regex pattern match against configured patterns.',
  },
]

export async function fetchProtectorConfig(): Promise<ProtectorConfig> {
  const res = await fetch(`${ENGINE_URL}/api/v1/guardrails/protector-config`)
  if (!res.ok) throw new Error(`Failed to fetch config: ${res.statusText}`)
  return res.json()
}

export async function saveProtectorConfig(cfg: ProtectorConfig): Promise<ProtectorConfig> {
  const res = await fetch(`${ENGINE_URL}/api/v1/guardrails/protector-config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      endpoint_url: cfg.endpoint_url,
      api_key: cfg.api_key,
      enabled_guardrails: cfg.enabled_guardrails,
    }),
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (body?.detail) detail = body.detail
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json()
}

export async function testProtectorConnection(): Promise<ProtectorTestResult> {
  const res = await fetch(`${ENGINE_URL}/api/v1/guardrails/protector-test`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(`Test failed: ${res.statusText}`)
  return res.json()
}
