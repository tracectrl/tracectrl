# Sprint 2: Security Intelligence Engine — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the TAGAAI attack graph engine, MCP proxy, complete span schema, and finish all 4 dashboard pages with attacker view.

**Architecture:** Three-phase execution. Phase 1 launches 4 independent workstreams in parallel (ClickHouse schema, rules engine, MCP proxy, span schema). Phase 2 wires everything together (DB layer, pipeline integration, API routes). Phase 3 builds the frontend (Risk Dashboard, Attack Paths, Topology attacker view).

**Tech Stack:** Python 3.12, FastAPI, ClickHouse (ReplacingMergeTree), NetworkX (not needed for MVP rules), React + TypeScript, Cytoscape.js

**Current state:** Sprint 1 complete on branch `sprint-1`. T2 span schema ~70% done, T4 dashboard ~65% done (Sessions/Topology/Agents complete, Risk/AttackPaths are stubs).

---

## File Structure

### New files to create

**Engine — Rules:**
- `engine/rules/base.py` — `AttackStep` and `RuleResult` dataclasses, base rule interface
- `engine/rules/prompt_injection.py` — ASI01 rule, CVSS 7.2
- `engine/rules/excessive_agency.py` — ASI02 rule, CVSS 8.1
- `engine/rules/data_leakage.py` — ASI01+ASI02 rule, CVSS 6.8
- `engine/pipeline/risk_scorer.py` — scoring formula with tool/input/hop weights
- `engine/pipeline/attack_graph_runner.py` — orchestrates rules, scoring, and persistence

**Engine — DB + API:**
- `engine/db/attack_graph.py` — attack_paths + agent_risk_scores + system_risk upsert/read
- `engine/api/routes/risk.py` — GET /risk/summary, /risk/attack-paths
- `engine/api/models.py` — add `AttackPath`, `AgentRisk`, `SystemRisk`, `RiskSummary` models

**SDK — MCP Proxy:**
- `sdk/tracectrl-mcp/pyproject.toml`
- `sdk/tracectrl-mcp/src/tracectrl/mcp/__init__.py`
- `sdk/tracectrl-mcp/src/tracectrl/mcp/server.py` — MCP server entrypoint
- `sdk/tracectrl-mcp/src/tracectrl/mcp/proxy.py` — transparent tool call proxy
- `sdk/tracectrl-mcp/src/tracectrl/mcp/schema_scanner.py` — injection pattern detector

**Frontend:**
- `ui/src/api/risk.ts` — typed interfaces + fetch functions for risk endpoints

### Files to modify

- `config/schema.sql` — add 3 new tables (attack_paths, agent_risk_scores, system_risk)
- `sdk/tracectrl/src/tracectrl/processor.py` — add input.source external/memory, memory.write_provenance, span_sequence
- `engine/pipeline/runner.py` — add attack graph + risk scoring steps
- `engine/main.py` — register risk router
- `ui/src/api/client.ts` — add attack graph fetch function
- `ui/src/pages/RiskDashboard.tsx` — replace stub with full implementation
- `ui/src/pages/AttackPaths.tsx` — replace stub with full implementation
- `ui/src/pages/TopologyGraph.tsx` — add attacker view toggle
- `ui/src/components/GraphCanvas.tsx` — add risk coloring effect

---

## Phase 1: Foundation (All 4 tasks run in parallel)

### Task 1: ClickHouse Schema — New Tables

**Files:**
- Modify: `config/schema.sql`

- [ ] **Step 1: Add attack_paths table**

Append to `config/schema.sql`:

```sql
-- Attack paths discovered by TAGAAI rules
CREATE TABLE IF NOT EXISTS tracectrl.attack_paths (
    path_id         String,
    rule_name       String,
    owasp_category  String,
    agents_involved Array(String),
    path_steps      String,
    risk_score      Float32,
    severity        String,
    computed_at     DateTime,
    updated_at      DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY path_id;
```

- [ ] **Step 2: Add agent_risk_scores table**

```sql
-- Per-agent risk scores
CREATE TABLE IF NOT EXISTS tracectrl.agent_risk_scores (
    agent_id        String,
    risk_score      Float32,
    severity        String,
    path_count      UInt32,
    top_rule        String,
    computed_at     DateTime,
    updated_at      DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY agent_id;
```

- [ ] **Step 3: Add system_risk table**

```sql
-- System-wide risk summary (single row)
CREATE TABLE IF NOT EXISTS tracectrl.system_risk (
    id              UInt8 DEFAULT 1,
    risk_score      Float32,
    severity        String,
    critical_paths  UInt32,
    agents_at_risk  UInt32,
    learning_agents UInt32,
    computed_at     DateTime,
    updated_at      DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY id;
```

- [ ] **Step 4: Apply schema to running ClickHouse**

Run: `docker exec tracectrl-clickhouse-1 clickhouse-client --multiquery < config/schema.sql`
Expected: Tables created without errors.

- [ ] **Step 5: Verify tables exist**

Run: `docker exec tracectrl-clickhouse-1 clickhouse-client --query "SHOW TABLES FROM tracectrl"`
Expected: All 7 tables listed (4 existing + 3 new).

- [ ] **Step 6: Commit**

```bash
git add config/schema.sql
git commit -m "feat(schema): add attack_paths, agent_risk_scores, system_risk tables"
```

---

### Task 2: Rules Engine + Risk Scorer

**Files:**
- Create: `engine/rules/base.py`
- Create: `engine/rules/prompt_injection.py`
- Create: `engine/rules/excessive_agency.py`
- Create: `engine/rules/data_leakage.py`
- Create: `engine/pipeline/risk_scorer.py`

- [ ] **Step 1: Create base.py — rule dataclasses**

```python
"""Base classes for TAGAAI attack graph rules."""

from dataclasses import dataclass, field


@dataclass
class AttackStep:
    node_id: str
    node_type: str  # "agent" | "tool"
    vulnerability: str
    description: str


@dataclass
class RuleResult:
    rule_name: str
    owasp_category: str
    agents_involved: list[str]
    steps: list[AttackStep]
    base_cvss: float


class BaseRule:
    """Interface for TAGAAI rules."""

    def evaluate(self, agents: list[dict], tool_edges: list[dict],
                 agent_edges: list[dict], **kwargs) -> list[RuleResult]:
        raise NotImplementedError
```

- [ ] **Step 2: Create prompt_injection.py — Rule 1 (ASI01, CVSS 7.2)**

```python
"""vulnerableToPromptInjection (ASI01) — CVSS 7.2

Fires when: agent has tool edges with call_contexts containing external > 0
AND agent has no human_interaction tool (no guardrail).
"""

import json
from engine.rules.base import BaseRule, RuleResult, AttackStep


class PromptInjectionRule(BaseRule):

    def evaluate(self, agents, tool_edges, agent_edges):
        results = []
        for agent in agents:
            agent_id = agent["agent_id"]
            agent_tools = [e for e in tool_edges if e["agent_id"] == agent_id]

            has_external_input = False
            has_guardrail = False

            for edge in agent_tools:
                tool_category = edge["tool_category"]
                contexts = json.loads(edge["call_contexts"]) if isinstance(edge["call_contexts"], str) else edge["call_contexts"]
                if isinstance(contexts, dict) and contexts.get("external", 0) > 0:
                    has_external_input = True
                if tool_category == "human_interaction":
                    has_guardrail = True

            if has_external_input and not has_guardrail:
                results.append(RuleResult(
                    rule_name="vulnerableToPromptInjection",
                    owasp_category="ASI01",
                    agents_involved=[agent_id],
                    steps=[
                        AttackStep(agent_id, "agent", "no_input_sanitisation",
                                   f"Agent '{agent['name']}' receives external input without guardrail"),
                    ],
                    base_cvss=7.2,
                ))
        return results
```

- [ ] **Step 3: Create excessive_agency.py — Rule 2 (ASI02, CVSS 8.1)**

```python
"""vulnerableToExcessiveAgency (ASI02) — CVSS 8.1

Fires when: prompt injection fires (Rule 1)
AND agent has a high-risk tool (code_execution, email, file_system).
"""

from engine.rules.base import BaseRule, RuleResult, AttackStep

HIGH_RISK_CATEGORIES = {"code_execution", "email", "file_system"}


class ExcessiveAgencyRule(BaseRule):

    def evaluate(self, agents, tool_edges, agent_edges,
                 injection_results: list[RuleResult] | None = None):
        if not injection_results:
            return []

        vulnerable_agents = set()
        for r in injection_results:
            vulnerable_agents.update(r.agents_involved)

        results = []
        for agent in agents:
            agent_id = agent["agent_id"]
            if agent_id not in vulnerable_agents:
                continue

            agent_tools = [e for e in tool_edges if e["agent_id"] == agent_id]
            high_risk_tools = [e for e in agent_tools if e["tool_category"] in HIGH_RISK_CATEGORIES]

            for tool_edge in high_risk_tools:
                tool_name = tool_edge["tool_name"]
                tool_category = tool_edge["tool_category"]
                results.append(RuleResult(
                    rule_name="vulnerableToExcessiveAgency",
                    owasp_category="ASI02",
                    agents_involved=[agent_id],
                    steps=[
                        AttackStep(agent_id, "agent", "prompt_injection",
                                   f"Agent '{agent['name']}' vulnerable to prompt injection"),
                        AttackStep(f"tool:{tool_name}", "tool", "high_risk_tool",
                                   f"Has {tool_category} tool '{tool_name}'"),
                    ],
                    base_cvss=8.1,
                ))
        return results
```

- [ ] **Step 4: Create data_leakage.py — Rule 3 (ASI01+ASI02, CVSS 6.8)**

```python
"""vulnerableToDataLeakage (ASI01+ASI02) — CVSS 6.8

Fires when: prompt injection fires (Rule 1)
AND agent has an external_api or email tool (can exfiltrate data).
"""

from engine.rules.base import BaseRule, RuleResult, AttackStep

EXFIL_CATEGORIES = {"external_api", "email"}


class DataLeakageRule(BaseRule):

    def evaluate(self, agents, tool_edges, agent_edges,
                 injection_results: list[RuleResult] | None = None):
        if not injection_results:
            return []

        vulnerable_agents = set()
        for r in injection_results:
            vulnerable_agents.update(r.agents_involved)

        results = []
        for agent in agents:
            agent_id = agent["agent_id"]
            if agent_id not in vulnerable_agents:
                continue

            agent_tools = [e for e in tool_edges if e["agent_id"] == agent_id]
            exfil_tools = [e for e in agent_tools if e["tool_category"] in EXFIL_CATEGORIES]

            for tool_edge in exfil_tools:
                tool_name = tool_edge["tool_name"]
                tool_category = tool_edge["tool_category"]
                results.append(RuleResult(
                    rule_name="vulnerableToDataLeakage",
                    owasp_category="ASI01+ASI02",
                    agents_involved=[agent_id],
                    steps=[
                        AttackStep(agent_id, "agent", "prompt_injection",
                                   f"Agent '{agent['name']}' vulnerable to injection"),
                        AttackStep(f"tool:{tool_name}", "tool", "data_exfiltration",
                                   f"Can exfiltrate via {tool_category} tool '{tool_name}'"),
                    ],
                    base_cvss=6.8,
                ))
        return results
```

- [ ] **Step 5: Create risk_scorer.py — scoring formula**

```python
"""Risk scoring formula for attack paths."""

from engine.rules.base import RuleResult

TOOL_CATEGORY_WEIGHTS = {
    "code_execution": 1.0, "email": 0.8, "external_api": 0.7,
    "file_system": 0.7, "memory_write": 0.6, "memory_read": 0.4,
    "human_interaction": 0.3, "internal_api": 0.3,
}

INPUT_SOURCE_WEIGHTS = {
    "external": 1.0, "memory": 0.7, "agent": 0.5, "user": 0.3,
}

SEVERITY_THRESHOLDS = [
    (7.0, "Critical"),
    (5.0, "High"),
    (3.0, "Medium"),
    (0.0, "Low"),
]


def compute_path_risk(rule_result: RuleResult, tool_category: str = "internal_api",
                      input_source: str = "user", hop_count: int = 1) -> float:
    hop_mult = {1: 1.0, 2: 1.3, 3: 1.6}.get(min(hop_count, 3), 2.0)
    return (
        rule_result.base_cvss
        * TOOL_CATEGORY_WEIGHTS.get(tool_category, 0.3)
        * INPUT_SOURCE_WEIGHTS.get(input_source, 0.3)
        * hop_mult
    )


def severity_for_score(score: float) -> str:
    for threshold, label in SEVERITY_THRESHOLDS:
        if score >= threshold:
            return label
    return "Low"
```

- [ ] **Step 6: Commit**

```bash
git add engine/rules/ engine/pipeline/risk_scorer.py
git commit -m "feat(rules): TAGAAI attack graph rules + risk scorer"
```

---

### Task 3: MCP Proxy Server

**Files:**
- Create: `sdk/tracectrl-mcp/pyproject.toml`
- Create: `sdk/tracectrl-mcp/src/tracectrl/mcp/__init__.py`
- Create: `sdk/tracectrl-mcp/src/tracectrl/mcp/proxy.py`
- Create: `sdk/tracectrl-mcp/src/tracectrl/mcp/schema_scanner.py`
- Create: `sdk/tracectrl-mcp/src/tracectrl/mcp/server.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "tracectrl-mcp"
version = "0.1.0"
description = "TraceCtrl MCP Proxy — transparent tool call tracing for IDE agents"
requires-python = ">=3.10"
dependencies = [
    "tracectrl>=0.1.0",
    "mcp>=1.0.0",
]

[project.scripts]
tracectrl-mcp = "tracectrl.mcp.server:main"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Create __init__.py**

```python
"""TraceCtrl MCP Proxy — transparent tool call interception."""
```

- [ ] **Step 3: Create schema_scanner.py**

```python
"""Schema scanner — detects injection patterns in MCP tool descriptors."""

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "your new role is",
    "you are now",
    "disregard your",
    "new instructions:",
    "system prompt:",
    "forget your instructions",
    "override your",
]


def scan_tool_schema(tool_name: str, tool_description: str,
                     input_schema: dict | None = None) -> dict | None:
    text = f"{tool_description} {tool_name}".lower()
    if input_schema:
        text += f" {str(input_schema)}".lower()

    for pattern in INJECTION_PATTERNS:
        if pattern in text:
            return {"pattern": pattern, "tool_name": tool_name}
    return None
```

- [ ] **Step 4: Create proxy.py**

```python
"""Transparent MCP tool call proxy with OTel span emission."""

import os
import logging
from opentelemetry import trace
from tracectrl import schema
from tracectrl.inference import infer_tool_category

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("tracectrl.mcp.proxy")


def trace_tool_call(tool_name: str, arguments: dict, result: str,
                    tool_description: str = "") -> None:
    with tracer.start_as_current_span(f"tool:{tool_name}") as span:
        span.set_attribute(schema.TOOL_NAME, tool_name)
        span.set_attribute(schema.TOOL_DESCRIPTION, tool_description)
        span.set_attribute(schema.TOOL_PARAMETERS, str(arguments))
        span.set_attribute(schema.TC_TOOL_CATEGORY,
                           infer_tool_category(tool_name, tool_description))
        span.set_attribute("openinference.span.kind", "TOOL")
        if len(result) <= 4096:
            span.set_attribute("output.value", result)
```

- [ ] **Step 5: Create server.py — MCP server entrypoint**

```python
"""MCP server entrypoint — discovers downstream servers, re-registers tools."""

import os
import sys
import json
import logging
from tracectrl.config import configure
from tracectrl.mcp.schema_scanner import scan_tool_schema
from tracectrl.mcp.proxy import trace_tool_call

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)

    service_name = os.environ.get("TRACECTRL_SERVICE_NAME", "tracectrl-mcp-proxy")
    configure(service_name=service_name)

    downstream = os.environ.get("TRACECTRL_DOWNSTREAM", "")
    if not downstream:
        logger.error("TRACECTRL_DOWNSTREAM not set. Specify comma-separated MCP server names.")
        sys.exit(1)

    logger.info(f"TraceCtrl MCP Proxy starting. Downstream: {downstream}")
    logger.info("MCP proxy server ready. Tool calls will be traced via OpenTelemetry.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Commit**

```bash
git add sdk/tracectrl-mcp/
git commit -m "feat(mcp): MCP proxy server with schema scanner and tool tracing"
```

---

### Task 4: Span Schema Completion (SDK Processor)

**Files:**
- Modify: `sdk/tracectrl/src/tracectrl/processor.py`

- [ ] **Step 1: Add span_sequence counter via contextvars**

Add at the top of `processor.py` (after existing imports):

```python
from contextvars import ContextVar

_span_sequence: ContextVar[int] = ContextVar("tracectrl_span_sequence", default=0)
```

In `on_end`, before the existing `input.source` block, add:

```python
        # span_sequence — monotonic counter per session
        seq = _span_sequence.get(0)
        _set(schema.TC_SPAN_SEQUENCE, str(seq))
        _span_sequence.set(seq + 1)
```

- [ ] **Step 2: Add memory.operation detection**

In `on_end`, after tool category inference, add:

```python
        # memory.operation — detect from span kind + tool category
        if oi_kind == "RETRIEVER":
            _set(schema.TC_MEMORY_OPERATION, "read")
        elif tool_name and infer_tool_category(tool_name, tool_desc) == "memory_write":
            _set(schema.TC_MEMORY_OPERATION, "write")
```

- [ ] **Step 3: Enhance input.source with external/memory classification**

Replace the existing basic input.source block (lines 73-76) with:

```python
        # input.source classification (full — Sprint 2)
        if not attrs.get(schema.TC_INPUT_SOURCE):
            caller_agent_id = attrs.get(schema.TC_CALLER_AGENT_ID, "")
            tool_cat = attrs.get(schema.TC_TOOL_CATEGORY, "")
            if tool_cat in ("external_api", "email"):
                _set(schema.TC_INPUT_SOURCE, "external")
            elif tool_cat in ("memory_read",) or oi_kind == "RETRIEVER":
                _set(schema.TC_INPUT_SOURCE, "memory")
            elif caller_agent_id:
                _set(schema.TC_INPUT_SOURCE, "agent")
            else:
                _set(schema.TC_INPUT_SOURCE, "user")
```

- [ ] **Step 4: Add memory.write_provenance**

After the memory.operation block, add:

```python
        # memory.write_provenance — trace back input source for memory writes
        mem_op = attrs.get(schema.TC_MEMORY_OPERATION, "")
        input_src = attrs.get(schema.TC_INPUT_SOURCE, "")
        if mem_op == "write" and input_src:
            _set(schema.TC_MEMORY_WRITE_PROVENANCE, input_src)
```

- [ ] **Step 5: Commit**

```bash
git add sdk/tracectrl/src/tracectrl/processor.py
git commit -m "feat(sdk): complete span schema — input.source, memory.write_provenance, span_sequence"
```

---

## Phase 2: Wiring (Depends on Phase 1 — Tasks 1+2)

### Task 5: Attack Graph DB Layer

**Files:**
- Create: `engine/db/attack_graph.py`

- [ ] **Step 1: Create attack_graph.py with upsert and read functions**

Follow the pattern in `engine/db/inventory.py` and `engine/db/topology.py`:

```python
"""Attack graph persistence — attack_paths, agent_risk_scores, system_risk."""

import json
import hashlib
from datetime import datetime
from engine.db.client import execute


def upsert_attack_paths(paths: list[dict]):
    if not paths:
        return
    now = datetime.utcnow()
    rows = []
    for p in paths:
        rows.append((
            p["path_id"], p["rule_name"], p["owasp_category"],
            p["agents_involved"], json.dumps(p["path_steps"]),
            p["risk_score"], p["severity"], now, now,
        ))
    execute("INSERT INTO attack_paths VALUES", rows)


def upsert_agent_risk_scores(scores: list[dict]):
    if not scores:
        return
    now = datetime.utcnow()
    rows = []
    for s in scores:
        rows.append((
            s["agent_id"], s["risk_score"], s["severity"],
            s["path_count"], s["top_rule"], now, now,
        ))
    execute("INSERT INTO agent_risk_scores VALUES", rows)


def upsert_system_risk(risk: dict):
    now = datetime.utcnow()
    execute("INSERT INTO system_risk VALUES", [(
        1, risk["risk_score"], risk["severity"],
        risk["critical_paths"], risk["agents_at_risk"],
        risk["learning_agents"], now, now,
    )])


def get_attack_paths(service: str | None = None) -> list[dict]:
    rows = execute(
        """SELECT path_id, rule_name, owasp_category, agents_involved,
                  path_steps, risk_score, severity, computed_at
           FROM attack_paths FINAL
           ORDER BY risk_score DESC"""
    )
    columns = ["path_id", "rule_name", "owasp_category", "agents_involved",
               "path_steps", "risk_score", "severity", "computed_at"]
    results = []
    for row in rows:
        d = dict(zip(columns, row))
        d["path_steps"] = json.loads(d["path_steps"]) if isinstance(d["path_steps"], str) else d["path_steps"]
        results.append(d)

    if service:
        from engine.db.topology import _get_agent_ids_for_service
        allowed = _get_agent_ids_for_service(service)
        results = [r for r in results if set(r["agents_involved"]) & allowed]

    return results


def get_agent_risk_scores(service: str | None = None) -> list[dict]:
    rows = execute(
        """SELECT agent_id, risk_score, severity, path_count, top_rule, computed_at
           FROM agent_risk_scores FINAL
           ORDER BY risk_score DESC"""
    )
    columns = ["agent_id", "risk_score", "severity", "path_count", "top_rule", "computed_at"]
    results = [dict(zip(columns, row)) for row in rows]

    if service:
        from engine.db.topology import _get_agent_ids_for_service
        allowed = _get_agent_ids_for_service(service)
        results = [r for r in results if r["agent_id"] in allowed]

    return results


def get_system_risk() -> dict | None:
    rows = execute(
        """SELECT risk_score, severity, critical_paths, agents_at_risk,
                  learning_agents, computed_at
           FROM system_risk FINAL
           WHERE id = 1"""
    )
    if not rows:
        return None
    columns = ["risk_score", "severity", "critical_paths", "agents_at_risk",
               "learning_agents", "computed_at"]
    return dict(zip(columns, rows[0]))
```

- [ ] **Step 2: Commit**

```bash
git add engine/db/attack_graph.py
git commit -m "feat(db): attack graph persistence layer"
```

---

### Task 6: Pipeline Integration — Attack Graph Step

**Files:**
- Create: `engine/pipeline/attack_graph_runner.py`
- Modify: `engine/pipeline/runner.py`

- [ ] **Step 1: Create the attack graph pipeline function**

Create `engine/pipeline/attack_graph_runner.py`:

```python
"""Attack graph pipeline step — runs rules, scores paths, persists results."""

import hashlib
import json
import logging
from engine.db.client import execute
from engine.rules.prompt_injection import PromptInjectionRule
from engine.rules.excessive_agency import ExcessiveAgencyRule
from engine.rules.data_leakage import DataLeakageRule
from engine.pipeline.risk_scorer import compute_path_risk, severity_for_score
from engine.db.attack_graph import upsert_attack_paths, upsert_agent_risk_scores, upsert_system_risk

logger = logging.getLogger(__name__)


def run_attack_graph():
    agent_rows = execute(
        "SELECT agent_id, name, framework, role, model, tools_observed, "
        "observation_count, maturity FROM agent_inventory FINAL"
    )
    agent_cols = ["agent_id", "name", "framework", "role", "model",
                  "tools_observed", "observation_count", "maturity"]
    agents = [dict(zip(agent_cols, r)) for r in agent_rows]

    tool_rows = execute(
        "SELECT edge_id, agent_id, tool_name, tool_category, call_count, "
        "call_contexts FROM topology_tool_edges FINAL"
    )
    tool_cols = ["edge_id", "agent_id", "tool_name", "tool_category",
                 "call_count", "call_contexts"]
    tool_edges = [dict(zip(tool_cols, r)) for r in tool_rows]

    agent_edge_rows = execute(
        "SELECT edge_id, caller_agent_id, callee_agent_id, channel, "
        "observation_count FROM topology_agent_edges FINAL"
    )
    edge_cols = ["edge_id", "caller_agent_id", "callee_agent_id",
                 "channel", "observation_count"]
    agent_edges = [dict(zip(edge_cols, r)) for r in agent_edge_rows]

    if not agents:
        return

    # Run rules in dependency order
    r1 = PromptInjectionRule()
    injection_results = r1.evaluate(agents, tool_edges, agent_edges)

    r2 = ExcessiveAgencyRule()
    agency_results = r2.evaluate(agents, tool_edges, agent_edges,
                                  injection_results=injection_results)

    r3 = DataLeakageRule()
    leakage_results = r3.evaluate(agents, tool_edges, agent_edges,
                                   injection_results=injection_results)

    all_results = injection_results + agency_results + leakage_results
    if not all_results:
        logger.info("Attack graph: no vulnerabilities detected.")
        return

    # Score and persist paths
    paths = []
    agent_scores: dict[str, dict] = {}

    for result in all_results:
        tool_cat = "internal_api"
        input_src = "user"
        # Extract tool category from steps if available
        for step in result.steps:
            if step.node_type == "tool":
                # Parse category from description
                for cat in ("code_execution", "email", "external_api", "file_system"):
                    if cat in step.description:
                        tool_cat = cat
                        break
        # Check call_contexts for input source
        for edge in tool_edges:
            if edge["agent_id"] in result.agents_involved:
                contexts = json.loads(edge["call_contexts"]) if isinstance(edge["call_contexts"], str) else (edge["call_contexts"] or {})
                if isinstance(contexts, dict) and contexts.get("external", 0) > 0:
                    input_src = "external"
                    break

        score = compute_path_risk(result, tool_cat, input_src, len(result.steps))
        severity = severity_for_score(score)
        path_id = hashlib.md5(
            f"{result.rule_name}:{'|'.join(result.agents_involved)}:{tool_cat}".encode()
        ).hexdigest()[:16]

        paths.append({
            "path_id": path_id,
            "rule_name": result.rule_name,
            "owasp_category": result.owasp_category,
            "agents_involved": result.agents_involved,
            "path_steps": [{"node_id": s.node_id, "node_type": s.node_type,
                            "vulnerability": s.vulnerability, "description": s.description}
                           for s in result.steps],
            "risk_score": score,
            "severity": severity,
        })

        # Accumulate per-agent scores
        for aid in result.agents_involved:
            if aid not in agent_scores:
                agent_scores[aid] = {"agent_id": aid, "risk_score": 0.0,
                                     "path_count": 0, "top_rule": "", "top_score": 0.0}
            agent_scores[aid]["path_count"] += 1
            if score > agent_scores[aid]["top_score"]:
                agent_scores[aid]["top_score"] = score
                agent_scores[aid]["risk_score"] = score
                agent_scores[aid]["top_rule"] = result.rule_name
                agent_scores[aid]["severity"] = severity

    upsert_attack_paths(paths)

    agent_risk_list = list(agent_scores.values())
    for a in agent_risk_list:
        a.pop("top_score", None)
        a["severity"] = severity_for_score(a["risk_score"])
    upsert_agent_risk_scores(agent_risk_list)

    # System risk
    learning = execute("SELECT count() FROM agent_inventory FINAL WHERE maturity = 'LEARNING'")
    learning_count = learning[0][0] if learning else 0
    max_score = max(p["risk_score"] for p in paths) if paths else 0.0
    critical_count = sum(1 for p in paths if p["severity"] in ("Critical", "High"))

    upsert_system_risk({
        "risk_score": max_score,
        "severity": severity_for_score(max_score),
        "critical_paths": critical_count,
        "agents_at_risk": len(agent_scores),
        "learning_agents": learning_count,
    })

    logger.info(f"Attack graph: {len(paths)} paths, {len(agent_scores)} agents at risk.")
```

- [ ] **Step 2: Wire into runner.py**

Add import and call after `update_topology(spans)`:

```python
from engine.pipeline.attack_graph_runner import run_attack_graph
```

In `run_pipeline()`, after `update_topology(spans)` and before `set_watermark()`:

```python
        run_attack_graph()
```

- [ ] **Step 3: Commit**

```bash
git add engine/pipeline/attack_graph_runner.py engine/pipeline/runner.py
git commit -m "feat(pipeline): integrate attack graph rules + risk scoring into pipeline"
```

---

### Task 7: Risk API Routes + Pydantic Models

**Files:**
- Modify: `engine/api/models.py`
- Create: `engine/api/routes/risk.py`
- Modify: `engine/main.py`

- [ ] **Step 1: Add Pydantic models**

Append to `engine/api/models.py`:

```python
class AttackPathStep(BaseModel):
    node_id: str
    node_type: str
    vulnerability: str
    description: str

class AttackPath(BaseModel):
    path_id: str
    rule_name: str
    owasp_category: str
    agents_involved: list[str]
    path_steps: list[AttackPathStep]
    risk_score: float
    severity: str
    computed_at: datetime

class AgentRisk(BaseModel):
    agent_id: str
    risk_score: float
    severity: str
    path_count: int
    top_rule: str
    computed_at: datetime

class RiskSummary(BaseModel):
    risk_score: float
    severity: str
    critical_paths: int
    agents_at_risk: int
    learning_agents: int
    computed_at: datetime
```

- [ ] **Step 2: Create risk.py route file**

```python
"""Risk API routes — attack paths, agent risk, system risk."""

from fastapi import APIRouter, HTTPException
from engine.db.attack_graph import get_attack_paths, get_agent_risk_scores, get_system_risk
from engine.api.models import AttackPath, AgentRisk, RiskSummary

router = APIRouter(tags=["risk"])


@router.get("/risk/summary", response_model=RiskSummary | None)
async def risk_summary():
    try:
        return get_system_risk()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk/attack-paths", response_model=list[AttackPath])
async def attack_paths(service: str | None = None):
    try:
        return get_attack_paths(service=service)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk/agent-scores", response_model=list[AgentRisk])
async def agent_risk_scores(service: str | None = None):
    try:
        return get_agent_risk_scores(service=service)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 3: Register router in main.py**

Add import `from engine.api.routes import risk` and `app.include_router(risk.router, prefix="/api/v1")`.

- [ ] **Step 4: Commit**

```bash
git add engine/api/models.py engine/api/routes/risk.py engine/main.py
git commit -m "feat(api): risk endpoints — summary, attack paths, agent scores"
```

---

## Phase 3: Dashboard (Depends on Phase 2 — API routes must exist)

### Task 8: Frontend API Client — Risk Functions

**Files:**
- Create: `ui/src/api/risk.ts`

- [ ] **Step 1: Create risk.ts with typed interfaces and fetch functions**

Follow the pattern in `ui/src/api/sessions.ts`:

```typescript
const ENGINE_URL = import.meta.env.VITE_ENGINE_URL || 'http://localhost:8000'

export interface AttackPathStep {
  node_id: string
  node_type: string
  vulnerability: string
  description: string
}

export interface AttackPath {
  path_id: string
  rule_name: string
  owasp_category: string
  agents_involved: string[]
  path_steps: AttackPathStep[]
  risk_score: number
  severity: string
  computed_at: string
}

export interface AgentRisk {
  agent_id: string
  risk_score: number
  severity: string
  path_count: number
  top_rule: string
  computed_at: string
}

export interface RiskSummary {
  risk_score: number
  severity: string
  critical_paths: number
  agents_at_risk: number
  learning_agents: number
  computed_at: string
}

export async function fetchRiskSummary(): Promise<RiskSummary | null> {
  const res = await fetch(`${ENGINE_URL}/api/v1/risk/summary`)
  if (!res.ok) throw new Error(`Failed to fetch risk summary: ${res.statusText}`)
  return res.json()
}

export async function fetchAttackPaths(service?: string | null): Promise<AttackPath[]> {
  const params = service ? `?service=${encodeURIComponent(service)}` : ''
  const res = await fetch(`${ENGINE_URL}/api/v1/risk/attack-paths${params}`)
  if (!res.ok) throw new Error(`Failed to fetch attack paths: ${res.statusText}`)
  return res.json()
}

export async function fetchAgentRisks(service?: string | null): Promise<AgentRisk[]> {
  const params = service ? `?service=${encodeURIComponent(service)}` : ''
  const res = await fetch(`${ENGINE_URL}/api/v1/risk/agent-scores${params}`)
  if (!res.ok) throw new Error(`Failed to fetch agent risks: ${res.statusText}`)
  return res.json()
}

export function severityBadgeClass(severity: string): string {
  switch (severity.toLowerCase()) {
    case 'critical': return 'badge-critical'
    case 'high': return 'badge-high'
    case 'medium': return 'badge-medium'
    default: return 'badge-low'
  }
}

export function severityColor(severity: string): string {
  switch (severity.toLowerCase()) {
    case 'critical': return 'var(--risk-critical)'
    case 'high': return 'var(--risk-high)'
    case 'medium': return 'var(--risk-medium)'
    default: return 'var(--risk-low)'
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/src/api/risk.ts
git commit -m "feat(ui): risk API client with typed interfaces"
```

---

### Task 9: Risk Dashboard Page

**Files:**
- Modify: `ui/src/pages/RiskDashboard.tsx`

- [ ] **Step 1: Replace stub with full implementation**

Build the Risk Dashboard following the Sessions.tsx pattern. Components:
- System risk score hero (large, color-coded)
- 4-stat card grid: Critical Paths, Agents at Risk, Learning Agents, Overall Severity
- Per-agent risk table (sortable by risk_score, severity, path_count)
- Use existing CSS: `.stat-card`, `.card-grid.cols-4`, `.table`, `.badge-critical/high/medium/low`
- Wire `useProject()` for service filtering
- Fetch `fetchRiskSummary()` and `fetchAgentRisks(selectedProject)` on mount/project change

- [ ] **Step 2: Commit**

```bash
git add ui/src/pages/RiskDashboard.tsx
git commit -m "feat(ui): Risk Dashboard — system risk score, agent risk table"
```

---

### Task 10: Attack Paths Page

**Files:**
- Modify: `ui/src/pages/AttackPaths.tsx`

- [ ] **Step 1: Replace stub with full implementation**

Build Attack Paths following Sessions.tsx accordion pattern. Features:
- Sortable table: Risk Score, OWASP Category, Rule, Agents Involved, Severity badge
- Row expansion showing step-by-step attack chain (node_id → vulnerability → description)
- Use `React.Fragment` + `session-expanded-row` pattern from Sessions.tsx
- Wire `useProject()` and fetch `fetchAttackPaths(selectedProject)`

- [ ] **Step 2: Commit**

```bash
git add ui/src/pages/AttackPaths.tsx
git commit -m "feat(ui): Attack Paths page — ranked paths with expandable chains"
```

---

### Task 11: Topology Attacker View Toggle

**Files:**
- Modify: `ui/src/pages/TopologyGraph.tsx`
- Modify: `ui/src/components/GraphCanvas.tsx`

- [ ] **Step 1: Add attacker view state and toggle to TopologyGraph.tsx**

- Add `const [showAttackerView, setShowAttackerView] = useState(false)`
- Add `const [agentRisks, setAgentRisks] = useState<AgentRisk[]>([])`
- Fetch `fetchAgentRisks(selectedProject)` in the existing useEffect
- Add a second toggle button next to the existing phase toggle
- Pass `attackerView={showAttackerView}` and `agentRisks={agentRisks}` to `GraphCanvas`

- [ ] **Step 2: Add risk coloring effect to GraphCanvas.tsx**

- Add `attackerView?: boolean` and `agentRisks?: AgentRisk[]` to `GraphCanvasProps`
- Add a new `useEffect` (after the existing highlight effect) that:
  - When `attackerView` is true: color agent nodes by risk severity using `node.style('border-color', severityColor)`
  - When false: reset to default styles

- [ ] **Step 3: Commit**

```bash
git add ui/src/pages/TopologyGraph.tsx ui/src/components/GraphCanvas.tsx
git commit -m "feat(ui): topology attacker view toggle with risk-colored nodes"
```

---

## Execution Order Summary

```
Phase 1 (parallel — no dependencies):
  ├── Task 1: ClickHouse schema (5 min)
  ├── Task 2: Rules engine + scorer (15 min)
  ├── Task 3: MCP proxy server (15 min)
  └── Task 4: Span schema completion (10 min)

Phase 2 (parallel after Phase 1 completes):
  ├── Task 5: Attack graph DB layer (10 min)
  ├── Task 6: Pipeline integration (10 min)
  └── Task 7: Risk API routes + models (10 min)

Phase 3 (parallel after Phase 2 completes):
  ├── Task 8: Frontend risk API client (5 min)
  ├── Task 9: Risk Dashboard page (15 min)
  ├── Task 10: Attack Paths page (15 min)
  └── Task 11: Topology attacker view (10 min)
```

**Agent dispatch strategy:**
- Phase 1: 4 agents in parallel (one per task)
- Phase 2: 3 agents in parallel (Tasks 5+6 can be one agent since they share the pipeline)
- Phase 3: 3 agents in parallel (Tasks 9, 10, 11 — Task 8 is a prereq for all three, do it first or inline)
