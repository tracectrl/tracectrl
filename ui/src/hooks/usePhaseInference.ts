import { useMemo } from 'react'
import { SpanDetail } from '../api/sessions'
import { getSpanType } from '../lib/spanUtils'

const PHASE_GAP_NS = 1_000_000_000 // 1 second gap = new phase

export interface PhaseGroup {
  phaseIndex: number
  agentNames: string[]
  agentIds: string[]  // topology node IDs (lowercase-hyphenated agent names)
  spanIds: Set<string>
  startNs: number
  endNs: number
}

export function usePhaseInference(spans: SpanDetail[]): PhaseGroup[] {
  return useMemo(() => {
    if (spans.length === 0) return []

    // Filter to AGENT spans, sort by start time
    const agentSpans = spans
      .filter(s => getSpanType(s).toUpperCase() === 'AGENT')
      .sort((a, b) => a.start_ns - b.start_ns)

    if (agentSpans.length === 0) return []

    const phases: PhaseGroup[] = []
    let currentPhase: PhaseGroup = {
      phaseIndex: 0,
      agentNames: [],
      agentIds: [],
      spanIds: new Set(),
      startNs: agentSpans[0].start_ns,
      endNs: agentSpans[0].start_ns + agentSpans[0].duration_ns,
    }

    for (const span of agentSpans) {
      if (span.start_ns - currentPhase.endNs > PHASE_GAP_NS) {
        // New phase
        phases.push(currentPhase)
        currentPhase = {
          phaseIndex: phases.length,
          agentNames: [],
          agentIds: [],
          spanIds: new Set(),
          startNs: span.start_ns,
          endNs: span.start_ns + span.duration_ns,
        }
      }

      const agentName = span.attributes['agent.name'] || span.attributes['tracectrl.agent.name'] || span.span_name.replace('.run', '')
      const agentId = (span.attributes['tracectrl.agent.id'] || span.attributes['agno.agent.id'] || agentName.toLowerCase().replace(/\s+/g, '-'))

      if (!currentPhase.agentNames.includes(agentName)) {
        currentPhase.agentNames.push(agentName)
      }
      if (!currentPhase.agentIds.includes(agentId)) {
        currentPhase.agentIds.push(agentId)
      }
      currentPhase.spanIds.add(span.span_id)
      currentPhase.endNs = Math.max(currentPhase.endNs, span.start_ns + span.duration_ns)
    }

    phases.push(currentPhase)
    return phases
  }, [spans])
}
