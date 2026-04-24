import { ENGINE_URL } from './config'

export interface ScanSummary {
  scan_id: string
  scanned_at: string
  openclaw_path: string
  profile: string
  check_count: number
  failed_count: number
  critical_count: number
  high_count: number
}

export interface ScanResult {
  scan_id: string
  scanned_at: string
  openclaw_path: string
  profile: string
  check_id: string
  section: string
  title: string
  severity: string
  passed: number
  finding: string
  remediation: string
  config_path: string
}

export interface ScanTopologyNode {
  id: string
  type: string
  label: string
  properties: Record<string, unknown>
}

export interface ScanTopologyEdge {
  id: string
  source: string
  target: string
  type: string
  properties: Record<string, unknown>
}

export interface ScanTopology {
  nodes: ScanTopologyNode[]
  edges: ScanTopologyEdge[]
}

export interface ScanDetail {
  scan_id: string | null
  results: ScanResult[]
  topology: ScanTopology | null
  config_changed?: boolean
  config_hash_at_scan?: string
  config_hash_current?: string
  days_since_scan?: number
  openclaw_path?: string
}

export interface PathValidationResponse {
  valid: boolean
  openclaw_json_found: boolean
  path: string
  error?: string
}

export interface ScanTriggerResponse {
  scan_id: string
  status: string
  started_at: string
}

export interface ScanStatusResponse {
  scan_id: string
  status: 'running' | 'complete' | 'failed'
  started_at: string
  completed_at?: string
  error?: string
  stored_scan_id?: string
}

export interface FixResponse {
  applied: string[]
  skipped: string[]
  errors: Record<string, string>
}

export async function fetchScans(): Promise<ScanSummary[]> {
  const res = await fetch(`${ENGINE_URL}/api/v1/scans`)
  if (!res.ok) throw new Error(`Failed to fetch scans: ${res.statusText}`)
  return res.json()
}

export async function fetchLatestScan(): Promise<ScanDetail> {
  const res = await fetch(`${ENGINE_URL}/api/v1/scans/latest`)
  if (!res.ok) throw new Error(`Failed to fetch latest scan: ${res.statusText}`)
  return res.json()
}

export async function fetchScanDetail(scanId: string): Promise<ScanDetail> {
  const res = await fetch(`${ENGINE_URL}/api/v1/scans/${scanId}`)
  if (!res.ok) throw new Error(`Failed to fetch scan: ${res.statusText}`)
  return res.json()
}

export async function validateWorkspacePath(path: string): Promise<PathValidationResponse> {
  const res = await fetch(`${ENGINE_URL}/api/v1/scan/validate-path`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
  if (!res.ok) throw new Error(`Failed to validate path: ${res.statusText}`)
  return res.json()
}

export async function triggerScan(workspacePath: string, profile?: 'L1' | 'L2'): Promise<ScanTriggerResponse> {
  const payload = { workspace_path: workspacePath, ...(profile ? { profile } : {}) }
  console.log('Trigger scan payload:', payload)

  const res = await fetch(`${ENGINE_URL}/api/v1/scan/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const errorText = await res.text()
    console.error('Trigger scan error response:', errorText)
    throw new Error(`Failed to trigger scan: ${res.statusText} - ${errorText}`)
  }

  return res.json()
}

export async function pollScanStatus(scanId: string): Promise<ScanStatusResponse> {
  const res = await fetch(`${ENGINE_URL}/api/v1/scan/status/${scanId}`)
  if (!res.ok) throw new Error(`Failed to fetch scan status: ${res.statusText}`)
  return res.json()
}

export async function applyFixes(workspacePath: string, checkIds: string[]): Promise<FixResponse> {
  const res = await fetch(`${ENGINE_URL}/api/v1/scan/fix`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ workspace_path: workspacePath, check_ids: checkIds }),
  })
  if (!res.ok) throw new Error(`Failed to apply fixes: ${res.statusText}`)
  return res.json()
}
