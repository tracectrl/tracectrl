const ENGINE_URL = import.meta.env.VITE_ENGINE_URL || 'http://localhost:8000'

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
  passed: boolean
  finding: string
  remediation: string
  config_path: string
}

export interface ScanDetail {
  scan_id: string | null
  results: ScanResult[]
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
