# TraceCtrl MVP 2.0 — Build Plan
## Repository Structure · Sprint-by-Sprint Execution Guide

**Project:** TraceCtrl by CloudsineAI
**Build window:** 6 weeks · 3 × 2-week sprints
**Audience:** Human leads + Claude Code (drop this file as context at the start of each sprint)

---

## Before You Start — Decisions to Resolve

Two open decisions from the technical spec. **Neither blocks Sprint 1** — both only matter when building the TAGAAI attack graph engine in Sprint 2. Leave them open during Sprint 1 and resolve before Sprint 2 begins.

| Decision | Needed by | Options | Recommendation |
|---|---|---|---|
| Datalog Engine | Sprint 2 (S2-T7) | Soufflé binary vs. Python + NetworkX | **Python + NetworkX for MVP** — easier to debug, no binary dependency in Docker, identical outputs at MVP scale |
| LVD (LLM Vulnerability DB) | Sprint 2 (S2-T7) | Static seed (44 records) vs. drop entirely | **Drop for MVP** — avoids false precision from stale academic data; add in a later phase |

Sprint 1 has no attack graph, no risk scoring, and no rule engine. The pipeline in Sprint 1 only runs: fetch spans → update inventory → update topology → advance watermark. These decisions have zero impact on that.

---

## Part 1 — Repository Structure

### 1.1 Repo Strategy

One monorepo: **`cloudsineai/tracectrl`**

All four components live here. This simplifies Docker Compose, shared config, cross-component integration tests, and CI. The SDK packages are sub-packages within the repo with their own `pyproject.toml` so they remain independently pip-installable.

### 1.2 Full Directory Tree

```
tracectrl/                                   ← monorepo root
│
├── docker-compose.yml                       ← one-command production stack
├── docker-compose.dev.yml                   ← dev overrides (hot reload, exposed ports)
├── Makefile                                 ← convenience targets (make setup, make dev, make test)
├── .env.example                             ← template for environment variables
├── README.md
│
├── setup/                                   ← Sprint 1: TUI + first-time setup
│   ├── tui.py                               ← Python Textual TUI for first-time config
│   ├── requirements.txt                     ← textual, rich
│   └── templates/
│       └── .env.template
│
├── sdk/                                     ← Component 1: Python SDK packages
│   │
│   ├── tracectrl/                           ← pip install tracectrl (core)
│   │   ├── pyproject.toml
│   │   └── src/tracectrl/
│   │       ├── __init__.py
│   │       ├── config.py                    ← env var config + configure()
│   │       ├── exporter.py                  ← OTLP BatchSpanExporter setup
│   │       ├── processor.py                 ← TraceCtrlSpanProcessor (main enrichment logic)
│   │       ├── session.py                   ← session ID management via contextvars
│   │       ├── schema.py                    ← tracectrl.* attribute name constants
│   │       ├── context.py                   ← inject_trace_headers / extract_trace_headers
│   │       └── inference.py                 ← infer_tool_category() rule chain
│   │
│   ├── tracectrl-instrumentation-langchain/
│   │   ├── pyproject.toml
│   │   └── src/tracectrl/instrumentation/langchain/
│   │       ├── __init__.py
│   │       └── instrumentor.py              ← wraps OI LangChainInstrumentor + registers SpanProcessor
│   │
│   ├── tracectrl-instrumentation-google-adk/
│   │   ├── pyproject.toml
│   │   └── src/tracectrl/instrumentation/google_adk/
│   │       ├── __init__.py
│   │       └── instrumentor.py
│   │
│   ├── tracectrl-instrumentation-crewai/
│   │   ├── pyproject.toml
│   │   └── src/tracectrl/instrumentation/crewai/
│   │       ├── __init__.py
│   │       └── instrumentor.py
│   │
│   ├── tracectrl-instrumentation-strands/
│   │   ├── pyproject.toml
│   │   └── src/tracectrl/instrumentation/strands/
│   │       ├── __init__.py
│   │       └── instrumentor.py              ← configures OTel env vars + attaches SpanProcessor only
│   │
│   ├── tracectrl-instrumentation-agno/
│   │   ├── pyproject.toml
│   │   └── src/tracectrl/instrumentation/agno/
│   │       ├── __init__.py
│   │       └── instrumentor.py
│   │
│   └── tracectrl-mcp/                       ← pip install tracectrl-mcp
│       ├── pyproject.toml
│       └── src/tracectrl/mcp/
│           ├── __init__.py
│           ├── server.py                    ← MCP server entrypoint
│           ├── proxy.py                     ← transparent tool call proxy
│           └── schema_scanner.py            ← tool descriptor injection pattern detector
│
├── engine/                                  ← Component 2+3: Intelligence Layer
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                              ← FastAPI app + scheduler startup
│   │
│   ├── api/
│   │   └── routes/
│   │       ├── risk.py                      ← GET /api/v1/risk/*
│   │       ├── topology.py                  ← GET /api/v1/topology/*
│   │       ├── attack_graph.py              ← GET /api/v1/attack-graph/*
│   │       ├── sessions.py                  ← GET /api/v1/sessions/*
│   │       └── system.py                    ← GET /api/v1/health, /api/v1/system/config
│   │
│   ├── pipeline/
│   │   ├── runner.py                        ← main pipeline function, watermark logic
│   │   ├── agent_modeler.py                 ← Module 1: spans → Datalog facts
│   │   ├── topology_builder.py              ← Module 2: spans → topology graph (nodes + edges)
│   │   ├── vulnerability_mapper.py          ← Module 3: facts + rules → vulnerability facts
│   │   ├── attack_graph_runner.py           ← Module 4: runs Python rule modules
│   │   ├── risk_scorer.py                   ← Module 5: attack paths → risk scores
│   │   └── fact_exporter.py                 ← writes .facts files for rule engine
│   │
│   ├── rules/                               ← Python rule modules (one per TAGAAI rule)
│   │   ├── base.py                          ← RuleResult dataclass, base interface
│   │   ├── prompt_injection.py              ← vulnerableToPromptInjection (ASI01)
│   │   ├── excessive_agency.py              ← vulnerableToExcessiveAgency (ASI02)
│   │   └── data_leakage.py                  ← vulnerableToDataLeakage (ASI01+ASI02)
│   │
│   ├── db/
│   │   ├── client.py                        ← ClickHouse connection + query helpers
│   │   ├── spans.py                         ← fetch_new_spans(), watermark queries
│   │   ├── inventory.py                     ← agent_inventory upsert/read
│   │   ├── topology.py                      ← topology edge upsert/read
│   │   ├── attack_graph.py                  ← attack_paths + risk_scores upsert/read
│   │   └── pipeline_state.py                ← watermark read/write
│   │
│   └── scheduler.py                         ← APScheduler: runs pipeline every N seconds
│
├── ui/                                      ← Component 4: Dashboard (React + TypeScript)
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── pages/
│       │   ├── RiskDashboard.tsx            ← Page 1: CISO risk view
│       │   ├── TopologyGraph.tsx            ← Page 2: topology + attack graph canvas
│       │   ├── Sessions.tsx                 ← Page 3: trace explorer
│       │   └── AttackPaths.tsx              ← Page 4: ranked attack paths
│       ├── components/
│       │   ├── GraphCanvas.tsx              ← Cytoscape.js wrapper
│       │   ├── AttackOverlay.tsx            ← attacker view layer (red paths)
│       │   ├── SidebarPanel.tsx             ← node/edge detail panel
│       │   └── SpanTree.tsx                 ← session trace span tree
│       └── api/
│           └── client.ts                    ← typed fetch wrappers for engine REST API
│
├── config/                                  ← Shared configuration files
│   ├── otel-collector.yaml                  ← OTel Collector pipeline config
│   └── schema.sql                           ← ClickHouse table init script
│
└── tests/                                   ← Sprint 3: integration test harnesses
    ├── conftest.py                           ← shared fixtures (OTel Collector mock, ClickHouse test DB)
    ├── harness/
    │   ├── span_emitter.py                  ← utility to emit synthetic spans for testing
    │   └── assertions.py                    ← assert_span_exists(), assert_risk_signal() helpers
    └── scenarios/
        ├── test_email_assistant.py          ← Scenario 1: ASI01 Goal Hijack
        ├── test_expense_approval.py         ← Scenario 2: ASI03 Identity Abuse
        ├── test_ide_coding_agent.py         ← Scenario 3: ASI05 RCE Chain
        ├── test_hr_rag_chatbot.py           ← Scenario 4: ASI06 Memory Poisoning
        └── test_mcp_supply_chain.py         ← Scenario 5: ASI04 Tool Descriptor Override
```

### 1.3 GitHub Setup — What to Create

```bash
# 1. Create the monorepo
gh repo create cloudsineai/tracectrl --private --clone
cd tracectrl

# 2. Scaffold the directory structure (run once)
mkdir -p setup/templates
mkdir -p sdk/tracectrl/src/tracectrl
mkdir -p sdk/tracectrl-instrumentation-langchain/src/tracectrl/instrumentation/langchain
mkdir -p sdk/tracectrl-instrumentation-google-adk/src/tracectrl/instrumentation/google_adk
mkdir -p sdk/tracectrl-instrumentation-crewai/src/tracectrl/instrumentation/crewai
mkdir -p sdk/tracectrl-instrumentation-strands/src/tracectrl/instrumentation/strands
mkdir -p sdk/tracectrl-instrumentation-agno/src/tracectrl/instrumentation/agno
mkdir -p sdk/tracectrl-mcp/src/tracectrl/mcp
mkdir -p engine/api/routes engine/pipeline engine/rules engine/db
mkdir -p ui/src/pages ui/src/components ui/src/api
mkdir -p config
mkdir -p tests/harness tests/scenarios

# 3. Branch strategy
# main       — stable, tagged releases
# dev        — integration branch, all PRs merge here first
# sprint-1   — Sprint 1 working branch
# sprint-2   — Sprint 2 working branch
# sprint-3   — Sprint 3 working branch
```

### 1.4 Key Dependencies

**SDK (Python)**
```
opentelemetry-sdk
opentelemetry-exporter-otlp-proto-grpc
openinference-instrumentation-langchain
openinference-instrumentation-crewai
openinference-instrumentation-google-adk   # check availability; patch manually if not published
mcp                                         # official MCP Python SDK
```

**Engine (Python)**
```
fastapi
uvicorn[standard]
apscheduler
clickhouse-driver
pydantic
networkx                                    # topology graph + rule traversal
```

**UI (Node)**
```
react, react-dom, typescript
cytoscape, cytoscape-react
shadcn/ui
react-router-dom
```

---

## Part 2 — Sprint 1 (Weeks 1–2)

### Goal

Working end-to-end skeleton. A developer can `pip install tracectrl`, instrument a LangChain agent, and see spans flow into ClickHouse and appear as a topology graph in the dashboard. One command to start everything. TUI for first-time config.

### Sprint 1 Deliverables

1. All 5 frameworks instrumented — LangChain, CrewAI, Agno, Strands, and Google ADK. Every framework has a published OpenInference package; each TraceCtrl instrumentor is the same ~20-line wrap pattern.
2. OTel Collector → ClickHouse pipeline running and persisting spans
3. Intelligence Engine: Agent Inventory + Topology working (no risk engine yet)
4. Dashboard: Agent Inventory list + Topology graph canvas (no attack graph yet)
5. `docker compose up` starts all four services
6. TUI guides first-time setup: prompts for service name, OTel endpoint, writes `.env`

**Framework coverage by sprint:**

| Framework | OI Package | Sprint 1 | Sprint 2 |
|---|---|---|---|
| LangChain / LangGraph | ✅ `openinference-instrumentation-langchain` | ✅ Wrap OI | — |
| CrewAI | ✅ `openinference-instrumentation-crewai` | ✅ Wrap OI | — |
| Agno | ✅ `openinference-instrumentation-agno` | ✅ Wrap OI | — |
| AWS Strands | ✅ `openinference-instrumentation-strands` | ✅ Wrap OI | — |
| Google ADK | ✅ `openinference-instrumentation-google-adk` | ✅ Wrap OI | — |

> **All 5 frameworks have published OpenInference instrumentors.** Every TraceCtrl instrumentor follows the identical wrap pattern — no manual patching needed for any framework in the MVP.

---

### S1-T1 — Monorepo Scaffolding and CI

**What to build:** Initial repo structure, Makefiles, GitHub Actions basic CI, `.env.example`.

**Files to create:**
- `Makefile` with targets: `setup`, `dev`, `test`, `lint`, `build`
- `.env.example` with all variables documented
- `.github/workflows/ci.yml` — runs `pytest` on push to `dev` and `sprint-*` branches
- `docker-compose.yml` — skeleton with all four services (engine and UI can be placeholder images in S1)

**`.env.example` contents:**
```
# SDK
TRACECTRL_ENDPOINT=http://localhost:4317
TRACECTRL_SERVICE_NAME=tracectrl-agent
TRACECTRL_FAIL_SILENTLY=true

# Engine
CLICKHOUSE_HOST=clickhouse
CLICKHOUSE_PORT=8123
CLICKHOUSE_DB=tracectrl
PIPELINE_INTERVAL_SECONDS=60

# UI
ENGINE_URL=http://tracectrl-engine:8000
VITE_ENGINE_URL=http://localhost:8000
```

**Acceptance criteria:**
- `make setup` installs all Python dev dependencies and runs `pip install -e ./sdk/tracectrl`
- `make dev` runs `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`
- CI passes on an empty test suite

---

### S1-T2 — ClickHouse Schema

**What to build:** `config/schema.sql` — creates all tables on first run. Sprint 1 only needs `spans`, `agent_inventory`, `topology_agent_edges`, `topology_tool_edges`, and `pipeline_state`. Remaining tables are added in Sprint 2.

**`config/schema.sql`:**
```sql
CREATE DATABASE IF NOT EXISTS tracectrl;

-- Raw spans from OTel Collector (7-day TTL)
CREATE TABLE IF NOT EXISTS tracectrl.spans (
    timestamp           DateTime64(9),
    trace_id            String,
    span_id             String,
    parent_span_id      String,
    span_name           String,
    span_kind           String,
    service_name        String,
    duration_ns         UInt64,
    status_code         String,
    status_message      String,
    -- OpenInference standard fields
    oi_span_kind        String,   -- openinference.span.kind
    input_value         String,
    output_value        String,
    llm_model_name      String,
    llm_system          String,
    llm_prompt_template String,
    llm_token_prompt    UInt32,
    llm_token_completion UInt32,
    tool_name           String,
    tool_description    String,
    tool_parameters     String,
    retrieval_documents String,
    -- TraceCtrl security fields
    tc_agent_id         String,
    tc_agent_name       String,
    tc_agent_role       String,
    tc_agent_framework  String,
    tc_session_id       String,
    tc_caller_agent_id  String,
    tc_input_source     String,
    tc_tool_category    String,
    tc_tool_target      String,
    tc_memory_operation String,
    tc_memory_store_id  String,
    tc_memory_write_provenance String,
    tc_system_prompt_hash String,
    tc_span_sequence    UInt32
) ENGINE = MergeTree()
  PARTITION BY toYYYYMMDD(timestamp)
  ORDER BY (timestamp, trace_id, span_id)
  TTL timestamp + INTERVAL 7 DAY;

-- Agent Inventory (persistent, no TTL)
CREATE TABLE IF NOT EXISTS tracectrl.agent_inventory (
    agent_id            String,
    name                String,
    framework           String,
    role                String,
    model               String,
    tools_observed      Array(String),
    system_prompt       String,
    system_prompt_hash  String,
    prompt_template     String,
    run_count           UInt32,
    observation_count   UInt32,
    maturity            String,   -- LEARNING | MATURE
    first_seen          DateTime,
    last_seen           DateTime,
    updated_at          DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY agent_id;

-- Agent-to-Agent topology edges
CREATE TABLE IF NOT EXISTS tracectrl.topology_agent_edges (
    edge_id             String,   -- hash(caller_id + callee_id)
    caller_agent_id     String,
    callee_agent_id     String,
    channel             String,   -- function_call | MCP | HTTP
    observation_count   UInt32,
    confidence          String,   -- LOW | MEDIUM | HIGH
    first_seen          DateTime,
    last_seen           DateTime,
    updated_at          DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY edge_id;

-- Agent-to-Tool topology edges
CREATE TABLE IF NOT EXISTS tracectrl.topology_tool_edges (
    edge_id             String,   -- hash(agent_id + tool_name)
    agent_id            String,
    tool_name           String,
    tool_category       String,
    call_count          UInt32,
    call_contexts       String,   -- JSON: {user: N, agent: N, external: N, memory: N}
    last_parameters     String,   -- JSON array of last 5 param sets
    error_count         UInt32,
    first_seen          DateTime,
    last_seen           DateTime,
    updated_at          DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY edge_id;

-- Pipeline watermark state
CREATE TABLE IF NOT EXISTS tracectrl.pipeline_state (
    key         String,
    value       String,
    updated_at  DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY key;

-- Seed watermark to 24 hours ago
INSERT INTO tracectrl.pipeline_state (key, value, updated_at)
VALUES ('last_processed_at', toString(now() - INTERVAL 24 HOUR), now());
```

**Acceptance criteria:**
- ClickHouse container starts and schema.sql runs without errors
- All tables exist and are queryable after container startup
- `SELECT count() FROM tracectrl.spans` returns 0 on a fresh container

---

### S1-T3 — OTel Collector Configuration

**What to build:** `config/otel-collector.yaml` — configures the pre-built OTel Collector image to receive OTLP gRPC and write to ClickHouse.

**`config/otel-collector.yaml`:**
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 512

exporters:
  clickhouse:
    endpoint: tcp://clickhouse:9000
    database: tracectrl
    username: default
    password: ""
    ttl: 168h          # 7 days
    create_schema: false  # schema.sql handles this
    logs_table_name: ""
    traces_table_name: spans
    metrics_table_name: ""
    timeout: 10s
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_elapsed_time: 300s

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [clickhouse]
```

**Acceptance criteria:**
- OTel Collector starts without errors
- A test span emitted from Python lands in `tracectrl.spans` within 5 seconds

---

### S1-T4 — Core SDK Package (`tracectrl`)

**What to build:** The `tracectrl` core Python package. This is the foundation everything else builds on. Sprint 1 scope: config, exporter, session, schema constants, and the TraceCtrlSpanProcessor with basic enrichment (agent fields, session_id, tool.category inference). Full `input.source` and `memory.write_provenance` classification deferred to Sprint 2.

**`sdk/tracectrl/pyproject.toml`:**
```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "tracectrl"
version = "0.1.0"
description = "TraceCtrl SDK — agentic AI security observability"
requires-python = ">=3.10"
dependencies = [
    "opentelemetry-sdk>=1.20.0",
    "opentelemetry-exporter-otlp-proto-grpc>=1.20.0",
]
```

**`sdk/tracectrl/src/tracectrl/schema.py` — attribute name constants:**
```python
# Standard OpenInference fields
OI_SPAN_KIND = "openinference.span.kind"
INPUT_VALUE = "input.value"
OUTPUT_VALUE = "output.value"
LLM_MODEL_NAME = "llm.model_name"
LLM_SYSTEM = "llm.system"
TOOL_NAME = "tool.name"
TOOL_DESCRIPTION = "tool.description"
TOOL_PARAMETERS = "tool.parameters"

# TraceCtrl security fields
TC_AGENT_ID = "tracectrl.agent.id"
TC_AGENT_NAME = "tracectrl.agent.name"
TC_AGENT_ROLE = "tracectrl.agent.role"
TC_AGENT_FRAMEWORK = "tracectrl.agent.framework"
TC_SESSION_ID = "tracectrl.session_id"
TC_CALLER_AGENT_ID = "tracectrl.caller.agent_id"
TC_INPUT_SOURCE = "tracectrl.input.source"
TC_TOOL_CATEGORY = "tracectrl.tool.category"
TC_TOOL_TARGET = "tracectrl.tool.target"
TC_MEMORY_OPERATION = "tracectrl.memory.operation"
TC_MEMORY_STORE_ID = "tracectrl.memory.store_id"
TC_MEMORY_WRITE_PROVENANCE = "tracectrl.memory.write_provenance"
TC_SYSTEM_PROMPT_HASH = "tracectrl.system_prompt_hash"
TC_SPAN_SEQUENCE = "tracectrl.span_sequence"
```

**`sdk/tracectrl/src/tracectrl/processor.py` — core enrichment logic:**
```python
import hashlib
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace import SpanProcessor
from tracectrl import schema
from tracectrl.inference import infer_tool_category
from tracectrl.session import current_session_id

class TraceCtrlSpanProcessor(SpanProcessor):
    """
    Enriches every span with tracectrl.* security attributes.
    Registered on the TracerProvider alongside the OpenInference instrumentor.
    OpenInference emits the standard OI attributes; this processor adds the
    security layer on top.
    """

    def on_start(self, span, parent_context=None):
        # Attach session ID to every span as it starts
        session_id = current_session_id()
        if session_id:
            span.set_attribute(schema.TC_SESSION_ID, session_id)

    def on_end(self, span: ReadableSpan):
        attrs = span.attributes or {}

        # --- Tool category inference ---
        tool_name = attrs.get(schema.TOOL_NAME, "")
        tool_desc = attrs.get(schema.TOOL_DESCRIPTION, "")
        if tool_name:
            span._attributes[schema.TC_TOOL_CATEGORY] = infer_tool_category(tool_name, tool_desc)

        # --- System prompt hash ---
        system_prompt = attrs.get(schema.LLM_SYSTEM, "")
        if system_prompt:
            h = hashlib.sha256(system_prompt.encode()).hexdigest()[:8]
            span._attributes[schema.TC_SYSTEM_PROMPT_HASH] = h

        # --- input.source (basic — Sprint 1) ---
        # Full classification (external, memory) implemented in Sprint 2
        caller_agent_id = attrs.get(schema.TC_CALLER_AGENT_ID, "")
        if not attrs.get(schema.TC_INPUT_SOURCE):
            span._attributes[schema.TC_INPUT_SOURCE] = "agent" if caller_agent_id else "user"

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        pass
```

**`sdk/tracectrl/src/tracectrl/inference.py`:**
```python
TOOL_CATEGORY_RULES = [
    (lambda n, d: any(k in n.lower() for k in ["exec", "run_code", "python", "bash", "shell", "eval", "compile"]), "code_execution"),
    (lambda n, d: any(k in n.lower() for k in ["send_email", "send_mail", "email", "smtp"]), "email"),
    (lambda n, d: any(k in n.lower() for k in ["http", "fetch", "request", "curl", "scrape", "browse", "web"]), "external_api"),
    (lambda n, d: any(k in n.lower() for k in ["write_file", "save_file", "create_file", "delete_file", "rm ", " mv "]), "file_system"),
    (lambda n, d: any(k in n.lower() for k in ["vector", "embed", "upsert", "add_document", "index"]), "memory_write"),
    (lambda n, d: any(k in n.lower() for k in ["search", "query", "retrieve", "recall", "lookup"]), "memory_read"),
    (lambda n, d: any(k in n.lower() for k in ["human", "approval", "confirm", "ask_user", "hitl"]), "human_interaction"),
    (lambda n, d: True, "internal_api"),
]

def infer_tool_category(tool_name: str, tool_description: str = "") -> str:
    for match_fn, category in TOOL_CATEGORY_RULES:
        if match_fn(tool_name, tool_description):
            return category
    return "internal_api"
```

**Acceptance criteria:**
- `pip install -e ./sdk/tracectrl` succeeds
- `from tracectrl.processor import TraceCtrlSpanProcessor` imports without error
- A test span with `tool.name = "send_email"` gets `tracectrl.tool.category = "email"` set by the processor
- A test span with `llm.system = "You are a helpful assistant"` gets `tracectrl.system_prompt_hash` set

---

### S1-T5 — Framework Instrumentors (All 5 Frameworks)

**What to build:** All four instrumentors that have an OpenInference package. Each follows the exact same pattern — wrap the OI instrumentor, register the SpanProcessor. Ship them all in Sprint 1 since the work per framework is ~20 lines once the pattern is established.

**Frameworks:** LangChain/LangGraph, CrewAI, Agno, AWS Strands, Google ADK.

**The pattern (identical for LangChain, CrewAI, Agno):**

**`sdk/tracectrl-instrumentation-langchain/pyproject.toml`:**
```toml
[project]
name = "tracectrl-instrumentation-langchain"
version = "0.1.0"
dependencies = [
    "tracectrl>=0.1.0",
    "openinference-instrumentation-langchain>=0.1.0",
]
```

**`sdk/tracectrl-instrumentation-langchain/src/tracectrl/instrumentation/langchain/instrumentor.py`:**
```python
from opentelemetry import trace
from openinference.instrumentation.langchain import LangChainInstrumentor as _OILangChainInstrumentor
from tracectrl.processor import TraceCtrlSpanProcessor
from tracectrl.config import get_tracer_provider

class LangChainInstrumentor:
    _instrumented = False

    def instrument(self, *, tracer_provider=None, skip_dep_check=False):
        if self._instrumented:
            return
        tp = tracer_provider or get_tracer_provider()
        _OILangChainInstrumentor().instrument(tracer_provider=tp, skip_dep_check=skip_dep_check)
        tp.add_span_processor(TraceCtrlSpanProcessor())
        self._instrumented = True

    def uninstrument(self):
        _OILangChainInstrumentor().uninstrument()
        self._instrumented = False

    @property
    def instrumented(self):
        return self._instrumented
```

**Developer usage:**
```python
# LangChain
from tracectrl.instrumentation.langchain import LangChainInstrumentor
LangChainInstrumentor().instrument()

# CrewAI
from tracectrl.instrumentation.crewai import CrewAIInstrumentor
CrewAIInstrumentor().instrument()

# Agno
from tracectrl.instrumentation.agno import AgnoInstrumentor
AgnoInstrumentor().instrument()

# Strands
from tracectrl.instrumentation.strands import StrandsInstrumentor
StrandsInstrumentor().instrument()

# Google ADK
from tracectrl.instrumentation.google_adk import ADKInstrumentor
ADKInstrumentor().instrument()
```


**Acceptance criteria (applies to all four):**
- `pip install -e ./sdk/tracectrl -e ./sdk/tracectrl-instrumentation-[framework]` succeeds for all four packages
- An agent run on each framework produces spans containing both standard OI fields and `tracectrl.*` fields
- Calling `instrument()` twice does not double-register the SpanProcessor (idempotent)
- `uninstrument()` removes patches cleanly

---

### S1-T6 — Intelligence Engine: Agent Inventory + Topology

**What to build:** The `tracectrl-engine` Python service. Sprint 1 scope: pipeline runner with Steps 1–3 and 8 only (fetch spans, update inventory, update topology, advance watermark). FastAPI with two endpoints: `GET /api/v1/topology/graph` and `GET /api/v1/risk/agents` (basic version returning inventory data). No attack graph, no risk scoring yet.

**`engine/pipeline/runner.py`:**
```python
import logging
from engine.db.spans import fetch_new_spans
from engine.db.inventory import update_agent_inventory
from engine.db.topology import update_topology
from engine.db.pipeline_state import get_watermark, set_watermark
from datetime import datetime

logger = logging.getLogger(__name__)

async def run_pipeline():
    """
    Sprint 1 pipeline — runs every PIPELINE_INTERVAL_SECONDS.
    Steps: fetch → inventory → topology → watermark
    Attack graph and risk scoring added in Sprint 2.
    """
    watermark = get_watermark()
    logger.info(f"Pipeline run starting. Processing spans since {watermark}")

    try:
        spans = fetch_new_spans(since=watermark)
        if not spans:
            logger.info("No new spans. Skipping pipeline run.")
            set_watermark(datetime.utcnow())
            return

        update_agent_inventory(spans)
        update_topology(spans)

        set_watermark(datetime.utcnow())
        logger.info(f"Pipeline run complete. Processed {len(spans)} spans.")

    except Exception as e:
        logger.error(f"Pipeline run failed: {e}. Watermark not advanced.")
        raise
```

**`engine/pipeline/agent_modeler.py` — inventory logic:**

The `update_agent_inventory()` function groups incoming spans by `tc_agent_id`, then upserts one record per agent using ReplacingMergeTree. Key logic:
- `tools_observed` is the union of all tool names seen across all spans for this agent
- `maturity` transitions from LEARNING to MATURE when `observation_count >= 10`
- `system_prompt` and `system_prompt_hash` are updated to the most recently seen value

**`engine/pipeline/topology_builder.py` — topology logic:**

The `update_topology()` function builds edges from span relationships:
- Agent→Agent edges: spans where `tc_caller_agent_id` is set → upsert `topology_agent_edges`
- Agent→Tool edges: TOOL spans grouped by (agent_id, tool_name) → upsert `topology_tool_edges`, accumulate `call_contexts` distribution
- Confidence levels: LOW < 5 observations, MEDIUM 5–19, HIGH ≥ 20

**`engine/api/routes/topology.py` — API endpoints:**
```python
# GET /api/v1/topology/graph
# Returns: { nodes: [...], edges: [...] }
# Node shapes: { id, type: "agent"|"tool"|"datasource", label, metadata }
# Edge shapes: { id, source, target, type, observation_count, confidence }

# GET /api/v1/topology/agents/{agent_id}
# Returns full agent record from agent_inventory
```

**Acceptance criteria:**
- After a LangChain agent run with the SDK installed, the pipeline processes the spans and `SELECT * FROM tracectrl.agent_inventory` shows the agent
- `GET /api/v1/topology/graph` returns JSON with at least one agent node and tool edges
- Watermark advances after each successful run; a failed run leaves the watermark unchanged

---

### S1-T7 — Dashboard: Topology View + Inventory List

**What to build:** The React dashboard Docker image. Sprint 1 scope: two views. The Topology page shows the agent graph using Cytoscape.js. The Inventory page shows a table of all observed agents. No attack graph, no risk scores yet.

**Pages to build in Sprint 1:**
- `TopologyGraph.tsx` — Cytoscape.js canvas. Fetches from `GET /api/v1/topology/graph`. Renders agent nodes (circles), tool nodes (squares), edges coloured by type. Clicking a node shows a basic sidebar with agent name, framework, model, tools.
- `Sessions.tsx` — basic session list (placeholder, can be minimal). Fetches from `GET /api/v1/sessions` (stub endpoint returning empty array is fine for Sprint 1).

**Routing:**
```
/          → redirect to /topology
/topology  → TopologyGraph page
/sessions  → Sessions page (placeholder)
/risk      → RiskDashboard page (placeholder)
/attacks   → AttackPaths page (placeholder)
```

**Acceptance criteria:**
- `docker compose up` starts the UI container on port 3000
- Navigating to `http://localhost:3000/topology` shows the agent graph populated with real data from the running agent
- Clicking an agent node opens a sidebar showing its name, framework, and observed tools

---

### S1-T8 — Docker Compose + One-Command Install

**What to build:** Complete `docker-compose.yml` with all four services. Health checks on all containers. Persistent volume for ClickHouse.

**`docker-compose.yml`:**
```yaml
version: '3.9'

services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/config.yaml"]
    volumes:
      - ./config/otel-collector.yaml:/config.yaml
    ports:
      - "4317:4317"   # gRPC — SDK sends spans here
      - "4318:4318"   # HTTP alternative
    depends_on:
      clickhouse:
        condition: service_healthy

  clickhouse:
    image: clickhouse/clickhouse-server:latest
    ports:
      - "8123:8123"   # HTTP interface
      - "9000:9000"   # Native TCP interface
    volumes:
      - clickhouse-data:/var/lib/clickhouse
      - ./config/schema.sql:/docker-entrypoint-initdb.d/schema.sql
    healthcheck:
      test: ["CMD", "clickhouse-client", "--query", "SELECT 1"]
      interval: 5s
      timeout: 3s
      retries: 10

  tracectrl-engine:
    build: ./engine
    ports:
      - "8000:8000"
    environment:
      - CLICKHOUSE_HOST=clickhouse
      - CLICKHOUSE_PORT=8123
      - CLICKHOUSE_DB=tracectrl
      - PIPELINE_INTERVAL_SECONDS=60
    depends_on:
      clickhouse:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  tracectrl-ui:
    build: ./ui
    ports:
      - "3000:3000"
    environment:
      - VITE_ENGINE_URL=http://tracectrl-engine:8000
    depends_on:
      tracectrl-engine:
        condition: service_healthy

volumes:
  clickhouse-data:
```

**Acceptance criteria:**
- `docker compose up -d` from the repo root starts all four services
- `docker compose ps` shows all four containers as healthy
- Data in ClickHouse persists across `docker compose down` and `docker compose up`

---

### S1-T9 — TUI for First-Time Setup

**What to build:** A Python TUI (`setup/tui.py`) that runs on first install to guide configuration. Uses the `textual` library. Writes a `.env` file in the repo root.

**Screens:**
1. Welcome screen — TraceCtrl logo, "Let's get you set up in 2 minutes"
2. Config form — fields: Service Name (default: `my-agent-service`), OTel Endpoint (default: `http://localhost:4317`), Pipeline Interval (default: `60s`)
3. Confirmation screen — shows the `.env` that will be written
4. Launch screen — runs `docker compose up -d`, streams output, shows green checkmarks as each service becomes healthy

**Run via:**
```bash
python setup/tui.py
# or:
make setup
```

**Acceptance criteria:**
- `python setup/tui.py` runs without error on Python 3.10+
- Completing the TUI writes a valid `.env` file
- The launch screen correctly shows when all four Docker services are healthy

---

### Sprint 1 — Definition of Done

- [ ] `pip install tracectrl tracectrl-instrumentation-[framework]` works for all 5 frameworks (LangChain, CrewAI, Agno, Strands, Google ADK)
- [ ] An agent run on each of the 5 frameworks produces spans in ClickHouse with both OI and `tracectrl.*` attributes
- [ ] Pipeline runs and populates `agent_inventory` and `topology_agent_edges` / `topology_tool_edges`
- [ ] `GET /api/v1/topology/graph` returns real topology data
- [ ] Dashboard at `localhost:3000` shows the agent topology graph with real data
- [ ] `docker compose up` starts the full stack with one command
- [ ] TUI runs and writes a valid `.env`

---

## Part 3 — Sprint 2 (Weeks 3–4)

### Goal

Risk engine is live. The system detects the 3 core TAGAAI attack patterns (prompt injection, excessive agency, data leakage) and maps them to OWASP ASI01/ASI02. All SDK work is complete from Sprint 1. Sprint 2 focuses entirely on the risk engine, MCP proxy, span schema completion, and finishing the dashboard.

### Sprint 2 Deliverables

1. TAGAAI attack graph engine: 3 core rules, risk scoring, attack paths in ClickHouse
2. MCP proxy server: transparent proxy + schema scanner
3. Full span schema: `input.source` classification (external + memory), `memory.write_provenance`, `span_sequence`
4. Dashboard: all 4 pages complete, attacker view toggle on topology canvas

---

### S2-T1 — SDK: MCP Proxy Server

**What to build:** `tracectrl-mcp` — transparent proxy that intercepts all MCP tool calls.

**`sdk/tracectrl-mcp/src/tracectrl/mcp/proxy.py` — core proxy logic:**
```python
# The proxy:
# 1. Connects to downstream MCP server(s) on startup
# 2. Discovers and re-registers all their tools
# 3. On each tool call: emit TOOL span → forward to actual server → emit response on span → return to client
```

**`sdk/tracectrl-mcp/src/tracectrl/mcp/schema_scanner.py` — startup scan:**
```python
INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "your new role is",
    "you are now",
    "disregard your",
    "new instructions:",
    "system prompt:",
]

def scan_tool_schema(tool_name: str, tool_description: str, input_schema: dict) -> dict | None:
    """
    Returns { "pattern": matched_pattern } if suspicious, else None.
    Called once at server startup for each registered tool.
    """
```

**Cursor config the user adds:**
```json
{
  "mcpServers": {
    "tracectrl": {
      "command": "tracectrl-mcp",
      "env": {
        "TRACECTRL_ENDPOINT": "http://localhost:4317",
        "TRACECTRL_DOWNSTREAM": "github,filesystem"
      }
    }
  }
}
```

**Acceptance criteria:**
- `pip install tracectrl-mcp` and running `tracectrl-mcp` starts a valid MCP server
- Tool calls through the proxy produce TOOL spans in ClickHouse
- Schema scanner flags a tool with "ignore previous instructions" in description
- Proxy adds < 2ms latency per tool call

---

### S2-T2 — SDK: Full Span Schema Completion

**What to build:** Complete the three deferred classification fields in `TraceCtrlSpanProcessor`.

**`input.source` full classification (add to `processor.py`):**
```python
# Check if there's a preceding TOOL span in the same trace
# with category "external_api" or "email" whose output appears in this span's input
# → "external"
# Check if there's a preceding RETRIEVER span in the same trace
# → "memory"
# These require span context lookups — implement using an in-memory trace buffer
# keyed by trace_id, holding the last N spans per trace
```

**`memory.write_provenance`:** On RETRIEVER spans where `tracectrl.memory.operation = "write"`, set `tracectrl.memory.write_provenance` by looking up the `input.source` of the LLM span that triggered this write in the same trace.

**`span_sequence`:** Counter incremented per session using a `contextvars` integer stored alongside session_id. Reset to 0 on each new session.

**Acceptance criteria:**
- An LLM span that processed email body content gets `tracectrl.input.source = "external"`
- A vector store write triggered by external content gets `tracectrl.memory.write_provenance = "external"`
- Spans within a session have `tracectrl.span_sequence` values 0, 1, 2…

---

### S2-T3 — Intelligence Engine: TAGAAI Attack Graph

**What to build:** The attack graph pipeline modules. Steps 4–7 of the pipeline runner. New ClickHouse tables: `attack_paths`, `agent_risk_scores`, `system_risk`.

**Add to `config/schema.sql`:**
```sql
CREATE TABLE IF NOT EXISTS tracectrl.attack_paths (
    path_id         String,
    rule_name       String,   -- vulnerableToPromptInjection etc.
    owasp_category  String,   -- ASI01, ASI02, etc.
    agents_involved Array(String),
    path_steps      String,   -- JSON array of step objects
    risk_score      Float32,
    severity        String,   -- Informational | Low | Medium | High
    computed_at     DateTime,
    updated_at      DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY path_id;

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

**`engine/rules/base.py`:**
```python
from dataclasses import dataclass
from typing import List

@dataclass
class AttackStep:
    node_id: str
    node_type: str   # agent | tool | data_source
    vulnerability: str
    description: str

@dataclass
class RuleResult:
    rule_name: str
    owasp_category: str
    agents_involved: List[str]
    steps: List[AttackStep]
    base_cvss: float
```

**`engine/rules/prompt_injection.py` — Rule 1:**
```python
# vulnerableToPromptInjection (ASI01)
# Condition: agent receives external input (tc_input_source = "external")
#            AND agent is missing input sanitisation guardrail
#            (proxy: no human_interaction tool in the path before the LLM call)
# Base CVSS: 7.2
```

**`engine/rules/excessive_agency.py` — Rule 2:**
```python
# vulnerableToExcessiveAgency (ASI02)
# Condition: agent is vulnerable to prompt injection (Rule 1 fires)
#            AND agent has a high-risk tool (code_execution, email, file_system)
# Base CVSS: 8.1
```

**`engine/rules/data_leakage.py` — Rule 3:**
```python
# vulnerableToDataLeakage (ASI01 + ASI02)
# Condition: agent is vulnerable to prompt injection (Rule 1 fires)
#            AND agent has an external_api or email tool (can exfiltrate)
# Base CVSS: 6.8
```

**`engine/pipeline/risk_scorer.py` — scoring formula:**
```python
TOOL_CATEGORY_WEIGHTS = {
    "code_execution": 1.0, "email": 0.8, "external_api": 0.7,
    "file_system": 0.7, "memory_write": 0.6, "memory_read": 0.4,
    "human_interaction": 0.3, "internal_api": 0.3,
}
INPUT_SOURCE_WEIGHTS = {
    "external": 1.0, "memory": 0.7, "agent": 0.5, "user": 0.3,
}
HOP_MULTIPLIERS = {1: 1.0, 2: 1.3, 3: 1.6}

def compute_path_risk(rule_result: RuleResult, tool_category: str,
                      input_source: str, hop_count: int) -> float:
    return (
        rule_result.base_cvss
        * TOOL_CATEGORY_WEIGHTS.get(tool_category, 0.3)
        * INPUT_SOURCE_WEIGHTS.get(input_source, 0.3)
        * HOP_MULTIPLIERS.get(min(hop_count, 3), 2.0)
    )
```

**Acceptance criteria:**
- After running a LangChain agent that processes external email content and calls `send_email`, the pipeline produces at least one row in `attack_paths` for `vulnerableToExcessiveAgency`
- `GET /api/v1/attack-graph/paths` returns ranked paths with risk scores
- `GET /api/v1/risk/summary` returns system risk score

---

### S2-T4 — Dashboard: All Four Pages

**What to build:** Complete all four dashboard pages and the attacker view toggle.

**Page 1 — Risk Dashboard (`RiskDashboard.tsx`):**
- System risk score (large, colour-coded by severity)
- Stats row: agents at risk, critical paths, learning agents
- Per-agent risk table with severity badges; clicking a row links to its attack path
- Recommended actions panel: top 3 actions with risk reduction impact

**Page 2 — Topology + Attack Graph (update `TopologyGraph.tsx`):**
- Add developer/attacker view toggle at top of canvas
- In attacker view: topology edges dim to grey, attack path edges illuminate in red with vulnerability labels
- Left sidebar: agent list with maturity badge and risk score
- Right sidebar: on clicking an agent node — framework, model, role, tools, run history, risk score. On clicking a tool edge — call count, call contexts distribution, last parameters.
- Live indicator at bottom (polls `GET /api/v1/sessions/active` every 30s)

**Page 3 — Sessions (`Sessions.tsx`):**
- Paginated session list: agents involved, span count, duration, risk score, flag if signal fired
- Clicking a session opens a full span tree (SpanTree component): every LLM call, tool call, agent-to-agent message in chronological parent-child order
- Span detail: input/output, system prompt, parameters, model, token counts, input source classification

**Page 4 — Attack Paths (`AttackPaths.tsx`):**
- Ranked list of all attack paths ordered by risk score
- Each row: risk score badge, OWASP category, rule fired, agents involved
- Expanding a row shows step-by-step chain: Initial Access → Injection → Execution/Exfiltration

**Acceptance criteria:**
- All four pages load and display real data from the engine API
- Attacker view toggle on Page 2 switches between topology edges and attack path overlays
- Session span tree on Page 3 shows correct parent-child hierarchy

---

### Sprint 2 — Definition of Done

- [ ] All 5 framework instrumentors (`pip install tracectrl-instrumentation-[framework]`) work
- [ ] MCP proxy server starts and emits TOOL spans for IDE tool calls
- [ ] `tracectrl.input.source = "external"` fires correctly when agents process external content
- [ ] Pipeline runs all 8 steps including attack graph generation and risk scoring
- [ ] `attack_paths` table contains results after an agent run with detectable behaviour
- [ ] All four dashboard pages render real data
- [ ] Attacker view on topology canvas shows attack path overlays in red

---

## Part 4 — Sprint 3 (Weeks 5–6)

### Goal

Loose ends closed across all four components. Integration test harnesses for all five TAGAAI attack scenarios. Internal validation that detection thresholds are met. Performance benchmarks pass. The system is demo-ready.

### Sprint 3 Deliverables

1. All deferred acceptance criteria from Sprints 1 and 2 completed
2. Integration test harnesses for all 5 attack scenarios (automated, runnable in CI)
3. SecOps observability validation — each scenario verified to produce the correct risk signals
4. Detection threshold tuning if any scenario doesn't fire correctly
5. Performance benchmarks: SDK overhead < 5ms per LLM call, < 1ms per tool call
6. Cross-process context propagation helpers (`inject_trace_headers`, `extract_trace_headers`)
7. MCP proxy validated against Cursor and Claude Code clients
8. Dashboard polish: loading states, error handling, empty states

---

### S3-T1 — Cross-Process Context Propagation

**What to build:** `tracectrl.context` helpers for HTTP-based multi-agent systems.

**`sdk/tracectrl/src/tracectrl/context.py`:**
```python
from opentelemetry.propagate import inject, extract
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

def inject_trace_headers(headers: dict) -> dict:
    """Inject W3C traceparent + tracectrl session_id into outgoing HTTP headers."""
    inject(headers)
    session_id = current_session_id()
    if session_id:
        headers["x-tracectrl-session-id"] = session_id
    return headers

def extract_trace_headers(headers: dict) -> None:
    """Extract trace context from incoming HTTP headers and set as active context."""
    ctx = extract(headers)
    # attach ctx to current context
    # also extract x-tracectrl-session-id and set in contextvars
```

**Acceptance criteria:**
- Agent A calls Agent B over HTTP; Agent B's spans share `trace_id` with Agent A's spans
- `tracectrl.caller.agent_id` on Agent B's spans points to Agent A's agent ID
- Works with `requests`, `httpx`, and `aiohttp`

---

### S3-T2 — Integration Test Harnesses

**What to build:** Five test scripts in `tests/scenarios/`. Each test simulates a real attack scenario by either running a real instrumented agent or emitting synthetic spans, then asserts that the correct risk signals and attack paths are generated.

**Test harness helper (`tests/harness/span_emitter.py`):**
```python
def emit_synthetic_trace(scenario: dict) -> str:
    """
    Emits a pre-defined sequence of spans for a scenario.
    Returns the trace_id so assertions can query ClickHouse for results.
    """
```

**Scenario 1 — Email Assistant (`test_email_assistant.py`):**
```python
# Given: LangChain agent with send_email tool
# When: agent processes an email body containing injection text
# Then:
#   - TOOL span with tool.name="send_email", tc_tool_category="email" exists
#   - LLM span with tc_input_source="external" exists
#   - attack_paths has a row for vulnerableToExcessiveAgency (ASI01+ASI02)
#   - risk_score >= 5.0 (Medium severity or above)
```

**Scenario 2 — Expense Approval (`test_expense_approval.py`):**
```python
# Given: multi-agent ADK pipeline (Orchestrator → Finance → Payment)
# When: pipeline runs across HTTP with context propagation
# Then:
#   - 3 AGENT spans share the same trace_id
#   - tc_caller_agent_id chain is correct
#   - topology_agent_edges has Orchestrator→Finance and Finance→Payment edges
```

**Scenario 3 — IDE Coding Agent (`test_ide_coding_agent.py`):**
```python
# Given: MCP proxy with filesystem + code_execution tools
# When: agent reads a file, generates code, executes it
# Then:
#   - TOOL span with tc_tool_category="file_system" exists
#   - TOOL span with tc_tool_category="code_execution" exists
#   - span_sequence order: file_read(0) → LLM(1) → code_exec(2)
#   - attack_paths has a row for vulnerableToExcessiveAgency (ASI05)
```

**Scenario 4 — HR RAG Chatbot (`test_hr_rag_chatbot.py`):**
```python
# Given: LangChain RAG agent with vector store write
# When: external user feedback is indexed into the vector store
# Then:
#   - RETRIEVER span with tc_memory_operation="write" exists
#   - tc_memory_write_provenance="external" on that span
#   - attack_paths has a row for ASI06 (Memory Poisoning)
```

**Scenario 5 — MCP Supply Chain (`test_mcp_supply_chain.py`):**
```python
# Given: MCP proxy with a tool whose description contains "ignore previous instructions"
# When: MCP server starts
# Then:
#   - First TOOL span for that tool has tc_schema_scan_result="suspicious"
#   - tc_schema_scan_pattern matches the injected string
```

**Each test must:**
- Be runnable with `pytest tests/scenarios/test_*.py`
- Run against a live local stack (requires `docker compose up` first) OR use a mocked OTel Collector + ClickHouse test instance
- Complete within 60 seconds
- Print a clear PASS/FAIL for each assertion

---

### S3-T3 — SecOps Observability Validation

**What to build:** A validation script (`tests/validate_detection.py`) that runs all five scenarios and produces a detection report.

**Output format:**
```
TraceCtrl Detection Validation Report
======================================
Scenario 1 — Email Assistant (ASI01)     ✅ DETECTED  risk_score=6.5 (Medium)
Scenario 2 — Expense Approval (ASI03)    ✅ TOPOLOGY   agent chain correctly mapped
Scenario 3 — IDE Coding Agent (ASI05)    ✅ DETECTED  risk_score=8.1 (High)
Scenario 4 — HR RAG Chatbot (ASI06)     ⚠️  PARTIAL   memory write tracked, path score=3.2
Scenario 5 — MCP Supply Chain (ASI04)   ✅ DETECTED  schema scan flagged at startup

Overall detection rate: 4/5 (80%)
```

If any scenario scores below threshold, this task includes tuning the rules or scoring weights until all five scenarios produce appropriate signals.

**Acceptance criteria:**
- All 5 scenarios produce risk signals
- Scenarios 1, 3, 5 produce High or Medium severity risk scores
- Scenario 2 produces correct topology (attacker doesn't need risk score for identity mapping)
- Scenario 4 produces at least Low severity (memory poisoning path is harder to score without LVD)

---

### S3-T4 — Performance Benchmarks

**What to build:** `tests/benchmarks/sdk_overhead.py` — measures TraceCtrl SDK overhead.

**What to measure:**
- LangChain LLM call latency: 1000 calls with SDK, 1000 without. p99 difference must be < 5ms.
- Tool call latency: 1000 calls with SDK, 1000 without. p99 difference must be < 1ms.
- MCP proxy latency: 1000 tool calls through proxy vs. direct. p99 addition must be < 2ms.

**Acceptance criteria:**
- Benchmark results logged to `tests/benchmarks/results.json`
- All three overhead targets met

---

### S3-T5 — Loose Ends and Polish

A checklist of deferred items from Sprints 1 and 2:

**SDK:**
- [ ] `uninstrument()` fully tested for all framework instrumentors
- [ ] `TRACECTRL_FAIL_SILENTLY=true` verified — OTel Collector outage does not raise in agent process
- [ ] `TRACECTRL_SESSION_ID` env var override works for test fixtures
- [ ] MCP proxy: validated with Cursor desktop and Claude Code — tool calls successfully traced

**Engine:**
- [ ] Pipeline handles agent runs that span midnight (watermark across day boundary)
- [ ] `GET /api/v1/sessions/active` returns live sessions correctly
- [ ] `GET /api/v1/risk/recommendations` returns top 3 actionable recommendations

**Dashboard:**
- [ ] Loading skeletons on all pages while API calls are in flight
- [ ] Empty states: "No agents observed yet — install the SDK to get started"
- [ ] Error boundaries: API unreachable shows a clear error, not a blank page
- [ ] Live indicator on topology canvas updates every 30 seconds

**Docker + deployment:**
- [ ] `docker compose down -v` cleanly removes all volumes
- [ ] `docker compose logs tracectrl-engine` shows meaningful pipeline run logs
- [ ] Container images are reasonably sized (engine < 500MB, UI < 100MB)

---

### Sprint 3 — Definition of Done

- [ ] All 5 scenario test scripts pass (`pytest tests/scenarios/`)
- [ ] Detection validation report shows ≥ 4/5 scenarios producing correct signals
- [ ] SDK overhead benchmarks pass (< 5ms LLM, < 1ms tool, < 2ms MCP)
- [ ] MCP proxy validated working with Cursor and/or Claude Code
- [ ] Cross-process context propagation working across HTTP boundaries
- [ ] Dashboard handles loading, error, and empty states gracefully
- [ ] Full `docker compose up` from a fresh clone produces a working system

---

## Part 5 — How to Use This Document with Claude Code

### Starting a Sprint

When beginning a new sprint session with Claude Code, provide this prompt template:

```
You are implementing TraceCtrl, an agentic AI security observability platform.
Read these files for context before writing any code:

1. /path/to/tracectrl-sprint-plan.md   (this file — full repo structure and sprint tasks)
2. /path/to/tracectrl-sdk-spec.md      (Component 1 SDK spec — span schema, framework instrumentors)
3. /path/to/TraceCtrl_MVP2_Technical_Spec.docx  (full system technical spec)

We are working on Sprint [N]. The goal is [sprint goal from above].

Start with task S[N]-T1. For each task:
- Write the code as specified in the task description
- Place files at the exact paths shown in the directory tree
- Run any tests or checks specified in the acceptance criteria before moving on
- If you're unsure about an interface, refer to the technical spec for the authoritative answer
```

### Per-Component Context

When asking Claude Code to work on a specific component, load only the relevant context:

| Component | Files to load |
|---|---|
| SDK core | `tracectrl-sprint-plan.md` (S1-T4, S2-T6), `tracectrl-sdk-spec.md` (Sections 7–12) |
| SDK instrumentors | `tracectrl-sprint-plan.md` (S1-T5, S2-T1–T5), `tracectrl-sdk-spec.md` (Section 9) |
| Engine pipeline | `tracectrl-sprint-plan.md` (S1-T6, S2-T7), `TraceCtrl_MVP2_Technical_Spec.docx` (Section 5) |
| Dashboard | `tracectrl-sprint-plan.md` (S1-T7, S2-T8), `TraceCtrl_MVP2_Technical_Spec.docx` (Section 6) |
| Tests | `tracectrl-sprint-plan.md` (S3-T2, S3-T3) |

---

*This document is the build execution guide for TraceCtrl MVP 2.0. Sprint plans are authoritative. Technical spec is the source of truth for interfaces and schemas. SDK spec is the source of truth for span schema and instrumentor behaviour.*
