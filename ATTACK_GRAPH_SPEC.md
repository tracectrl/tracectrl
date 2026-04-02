# TraceCtrl Attack Graph — Implementation Spec
> Sprint 2 build spec. Feed directly to Claude Code.

## Resolved Open Decisions
- **Datalog engine**: Python rule engine (no Soufflé binary). NetworkX for graph traversal.
- **LVD**: Dropped for MVP. Use tool category weights + CVSS baselines defined below.

---

## 1. DB Schema — add to `config/schema.sql`

```sql
CREATE TABLE IF NOT EXISTS tracectrl.attack_paths (
    path_id          String,
    rule_id          String,
    severity         String,       -- CRITICAL | HIGH | MEDIUM | LOW
    owasp_tag        String,       -- e.g. ASI01, ASI02
    title            String,
    description      String,
    agent_id         String,
    path_nodes       Array(String),
    path_edges       Array(String),
    risk_score       Float32,
    detected_at      DateTime,
    updated_at       DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY path_id;
```

---

## 2. Backend — new files

### `engine/pipeline/attack_graph.py`

**Purpose**: Derive Datalog facts from topology tables, apply 3 MVP rules, score paths, write to `attack_paths`.

#### Datalog Facts (derived from ClickHouse)

Query `topology_tool_edges FINAL` and `topology_agent_edges FINAL` to build:

```python
# execCode(agent_id, tool_name, tool_category)
# → every row in topology_tool_edges

# externalInteraction(agent_id, tool_name)
# → tool_edges where call_contexts['external'] > 0

# memoryInteraction(agent_id, tool_name)
# → tool_edges where call_contexts['memory'] > 0

# hasHighRiskTool(agent_id)
# → agent has any tool with category in {code_execution, email, file_system}

# hasExternalOutbound(agent_id)
# → agent has any tool with category = external_api

# missingGuardrail(agent_id)
# → agent has externalInteraction BUT no human_interaction tool in their tool edges

# agentCalls(caller_id, callee_id)
# → every row in topology_agent_edges
```

#### The 3 MVP Rules

```python
def rule_prompt_injection(facts) -> list[Finding]:
    """
    vulnerableToPromptInjection:
      externalInteraction(Agent, _) AND missingGuardrail(Agent)
    CVSS base: 7.2 | OWASP: ASI01
    """

def rule_excessive_agency(facts, injection_agents) -> list[Finding]:
    """
    vulnerableToExcessiveAgency:
      vulnerableToPromptInjection(Agent) AND hasHighRiskTool(Agent)
    CVSS base: 8.1 | OWASP: ASI02
    High-risk tools: code_execution, email, file_system
    """

def rule_data_leakage(facts, injection_agents) -> list[Finding]:
    """
    vulnerableToDataLeakage:
      vulnerableToPromptInjection(Agent) AND hasExternalOutbound(Agent)
    CVSS base: 6.8 | OWASP: ASI01+ASI02
    """
```

Rules 2 and 3 only fire for agents where Rule 1 already fired. Pass `injection_agents: set[str]` from Rule 1 into Rules 2 and 3.

#### Risk Score Formula

```
risk_score = cvss_base × tool_category_weight × input_source_weight × hop_multiplier

tool_category_weight:  code_execution=1.0, email=0.8, external_api=0.7,
                       file_system=0.7, memory_write=0.6, memory_read=0.4, internal_api=0.3

input_source_weight:   external=1.0, memory=0.7, agent=0.5, user=0.3

hop_multiplier:        1 hop=1.0, 2 hops=1.3, 3 hops=1.6, 4+ hops=2.0
```

Hop count = number of agent→agent edges in the path before reaching the vulnerable tool.

#### Severity Thresholds
```
0.0–2.9  → LOW
3.0–4.9  → MEDIUM  (not surfaced in main dashboard)
5.0–7.4  → HIGH
7.5–10.0 → CRITICAL
```

#### `generate_attack_paths()` — main entry point

```python
def generate_attack_paths() -> None:
    """Called from runner.py after update_topology(). Reads topology tables,
    derives facts, runs 3 rules, scores paths, upserts to attack_paths table."""
```

Each finding gets a deterministic `path_id = md5(rule_id + agent_id + tool_name)[:16]`.

`path_nodes`: list of node IDs in order, e.g. `["external_input", "agent-x", "tool:send_email"]`
`path_edges`: list of edge IDs from topology tables that form the path

---

### `engine/api/routes/attack_graph.py`

Two endpoints:

```
GET /api/v1/attack-graph/paths
  Response: { paths: [{ path_id, rule_id, severity, owasp_tag, title, description,
                        agent_id, path_nodes, path_edges, risk_score, detected_at }] }
  Sorted by risk_score DESC.

GET /api/v1/attack-graph/overlay
  Response: { compromised_nodes: [{ node_id, severity, risk_score }],
              attack_edges: [{ source, target, rule_id, severity }] }
  Used by frontend to render the Attacker View overlay on the topology canvas.
```

---

## 3. Backend — modified files

### `engine/pipeline/runner.py`

Add after `update_topology(spans)`:
```python
from engine.pipeline.attack_graph import generate_attack_paths
# ...
generate_attack_paths()  # Step 4: derive attack paths from updated topology
```

### `engine/api/routes/__init__.py` or `engine/main.py`

Register the new router:
```python
from engine.api.routes.attack_graph import router as attack_graph_router
app.include_router(attack_graph_router, prefix="/api/v1")
```

---

## 4. Frontend — modified files

### `ui/src/api/client.ts`

Add:
```typescript
export interface AttackPath {
  path_id: string
  rule_id: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  owasp_tag: string
  title: string
  description: string
  agent_id: string
  path_nodes: string[]
  path_edges: string[]
  risk_score: number
  detected_at: string
}

export interface AttackOverlay {
  compromised_nodes: { node_id: string; severity: string; risk_score: number }[]
  attack_edges: { source: string; target: string; rule_id: string; severity: string }[]
}

export async function fetchAttackPaths(): Promise<AttackPath[]>
export async function fetchAttackOverlay(): Promise<AttackOverlay>
```

### `ui/src/pages/TopologyGraph.tsx`

1. Add state: `const [attackMode, setAttackMode] = useState(false)`
2. Add state: `const [overlay, setOverlay] = useState<AttackOverlay | null>(null)`
3. Fetch overlay when `attackMode` becomes true (lazy — only fetch when toggled)
4. Add toggle button next to "Show Phases":
   ```tsx
   <button
     className={`phase-toggle${attackMode ? ' active' : ''}`}
     onClick={() => setAttackMode(prev => !prev)}
   >
     Attack Surface
   </button>
   ```
5. Pass `attackMode` and `overlay` as props to `GraphCanvas`
6. When `attackMode` is on, render `<AttackFindingsPanel>` in place of (or alongside) `SidebarPanel`

### `ui/src/components/GraphCanvas.tsx`

Add props:
```typescript
attackMode?: boolean
overlay?: AttackOverlay | null
```

When `attackMode` is true, apply these Cytoscape style overrides in a `useEffect` that watches `[attackMode, overlay]`:

```javascript
// Dim all existing edges
cy.edges().style({ opacity: 0.15 })

// Risk-colour compromised agent nodes
// CRITICAL → #EF4444 (red), HIGH → #F97316 (orange),
// MEDIUM → #EAB308 (yellow), LOW → unchanged
overlay.compromised_nodes.forEach(({ node_id, severity }) => {
  cy.$(`#${node_id}`).style({ 'background-color': severityColor(severity) })
})

// Highlight attack path edges in red, thicker
overlay.attack_edges.forEach(({ source, target }) => {
  cy.edges(`[source="${source}"][target="${target}"]`).style({
    'line-color': '#EF4444',
    'target-arrow-color': '#EF4444',
    width: 3,
    opacity: 1
  })
})
```

When `attackMode` is false, restore all original styles (reset via `cy.elements().removeStyle()`).

Update legend to show risk colours when `attackMode` is on.

---

## 5. Frontend — new file

### `ui/src/components/AttackFindingsPanel.tsx`

A slide-in panel (same pattern as `SidebarPanel`). Props: `paths: AttackPath[]`, `onClose: () => void`.

Renders a ranked list sorted by `risk_score` DESC. Each card:
- Severity badge (coloured pill: CRITICAL/HIGH/MEDIUM/LOW)
- Title + OWASP tag
- Path chain: `external_input → AgentName → tool_name` (derived from `path_nodes`)
- Risk score (e.g. `8.1`)
- One-line description

No expand/collapse needed for MVP. Keep it simple.

---

## File Summary

| Action | File |
|--------|------|
| ADD table | `config/schema.sql` |
| NEW | `engine/pipeline/attack_graph.py` |
| NEW | `engine/api/routes/attack_graph.py` |
| MODIFY | `engine/pipeline/runner.py` |
| MODIFY | `engine/main.py` (register router) |
| MODIFY | `ui/src/api/client.ts` |
| MODIFY | `ui/src/pages/TopologyGraph.tsx` |
| MODIFY | `ui/src/components/GraphCanvas.tsx` |
| NEW | `ui/src/components/AttackFindingsPanel.tsx` |
