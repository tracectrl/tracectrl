import { ScanResult, ScanTopology } from '../api/scan'

export interface NodeChange {
  nodeId: string
  label: string
  type: 'added' | 'removed' | 'modified'
  property?: string
  oldValue?: unknown
  newValue?: unknown
}

export interface VulnerabilityChange {
  severity: string
  delta: number // positive = new findings, negative = resolved
}

export interface FindingChange {
  checkId: string
  title: string
  severity: string
  type: 'added' | 'resolved' // added = newly failing, resolved = newly passing
}

export interface ScanDiff {
  nodeChanges: NodeChange[]
  vulnerabilityChanges: {
    critical: number
    high: number
    medium: number
    low: number
  }
  findingChanges: FindingChange[]
  totalVulnDelta: number
  hasChanges: boolean
}

export function computeScanDiff(
  oldTopology: ScanTopology | null,
  newTopology: ScanTopology | null,
  oldResults: ScanResult[],
  newResults: ScanResult[]
): ScanDiff {
  const nodeChanges: NodeChange[] = []
  const oldNodes = new Map(oldTopology?.nodes.map(n => [n.id, n]) ?? [])
  const newNodes = new Map(newTopology?.nodes.map(n => [n.id, n]) ?? [])

  // Detect added nodes
  for (const [id, node] of newNodes) {
    if (!oldNodes.has(id)) {
      nodeChanges.push({
        nodeId: id,
        label: node.label,
        type: 'added',
      })
    }
  }

  // Detect removed nodes
  for (const [id, node] of oldNodes) {
    if (!newNodes.has(id)) {
      nodeChanges.push({
        nodeId: id,
        label: node.label,
        type: 'removed',
      })
    }
  }

  // Detect property changes for all configuration fields
  for (const [id, newNode] of newNodes) {
    const oldNode = oldNodes.get(id)
    if (!oldNode) continue

    // Check for property changes
    const oldProps = oldNode.properties || {}
    const newProps = newNode.properties || {}

    // Get all unique property keys from both old and new
    const allKeys = new Set([...Object.keys(oldProps), ...Object.keys(newProps)])

    for (const key of allKeys) {
      const oldValue = oldProps[key]
      const newValue = newProps[key]

      // Skip if values are the same
      if (JSON.stringify(oldValue) === JSON.stringify(newValue)) continue

      // Skip internal/display-only fields that aren't real config changes
      if (key === 'token_tail' || key === 'api_key_tail' || key === 'credential_tail') continue
      if (key === 'soul_excerpt') continue

      nodeChanges.push({
        nodeId: id,
        label: newNode.label,
        type: 'modified',
        property: key,
        oldValue,
        newValue,
      })
    }
  }

  // Compute vulnerability changes
  const oldSeverityCounts = countBySeverity(oldResults)
  const newSeverityCounts = countBySeverity(newResults)

  const vulnerabilityChanges = {
    critical: newSeverityCounts.critical - oldSeverityCounts.critical,
    high: newSeverityCounts.high - oldSeverityCounts.high,
    medium: newSeverityCounts.medium - oldSeverityCounts.medium,
    low: newSeverityCounts.low - oldSeverityCounts.low,
  }

  const totalVulnDelta =
    vulnerabilityChanges.critical +
    vulnerabilityChanges.high +
    vulnerabilityChanges.medium +
    vulnerabilityChanges.low

  // Compute individual finding changes
  const findingChanges: FindingChange[] = []
  const oldFailingChecks = new Map(
    oldResults.filter(r => r.passed !== 1).map(r => [r.check_id, r])
  )
  const newFailingChecks = new Map(
    newResults.filter(r => r.passed !== 1).map(r => [r.check_id, r])
  )

  // Find newly failing checks (added vulnerabilities)
  for (const [checkId, result] of newFailingChecks) {
    if (!oldFailingChecks.has(checkId)) {
      findingChanges.push({
        checkId,
        title: result.title,
        severity: result.severity.toLowerCase(),
        type: 'added',
      })
    }
  }

  // Find newly passing checks (resolved vulnerabilities)
  for (const [checkId, result] of oldFailingChecks) {
    if (!newFailingChecks.has(checkId)) {
      findingChanges.push({
        checkId,
        title: result.title,
        severity: result.severity.toLowerCase(),
        type: 'resolved',
      })
    }
  }

  const hasChanges = nodeChanges.length > 0 || totalVulnDelta !== 0

  return {
    nodeChanges,
    vulnerabilityChanges,
    findingChanges,
    totalVulnDelta,
    hasChanges,
  }
}

function countBySeverity(results: ScanResult[]): Record<string, number> {
  const counts = { critical: 0, high: 0, medium: 0, low: 0 }
  for (const r of results) {
    if (r.passed === 1) continue
    const sev = r.severity.toLowerCase()
    if (sev in counts) {
      counts[sev as keyof typeof counts]++
    }
  }
  return counts
}
