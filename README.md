# TraceCtrl

**Security Observability & Control for Agentic AI**

TraceCtrl gives security teams and developers complete visibility into every agent action, tool call, and data access — with runtime protection and attack graph risk scoring powered by TAGAAI.

Built by [CloudsineAI](https://cloudsine.ai).

---

## Features

- **TAGAAI Attack Graph Engine** — Automated vulnerability detection with 3 built-in rules: prompt injection (ASI-01), excessive agency (ASI-02), and data leakage (ASI-01 + ASI-02). Risk scores use a CVSS-based formula combining base severity, exploitability, and blast radius.
- **MCP Proxy Server** — Transparent proxy for IDE agent tracing (Cursor, Claude Code). Captures every tool call made through MCP-compatible agents without code changes.
- **Full Span Schema** — Security-enriched OpenTelemetry spans with `input.source` classification (`user`, `agent`, `external`, `memory`), memory write provenance, and span sequencing.
- **5 Dashboard Pages** — Topology (developer + attacker view), Sessions (trace explorer), Agents (inventory), Risk Dashboard (system-level scoring), and Attack Paths (ranked vulnerability chains).
- **5 Framework Instrumentors** — LangChain, CrewAI, Agno, Google ADK, AWS Strands — each requiring only 3 lines of code.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Your Agent (Python)                                                │
│  ┌───────────────┐  ┌─────────────────────┐  ┌──────────────────┐  │
│  │ tracectrl SDK  │→ │ Framework           │→ │ TraceCtrl        │  │
│  │ configure()    │  │ Instrumentor (OI)   │  │ SpanProcessor    │  │
│  └───────────────┘  └─────────────────────┘  └──────┬───────────┘  │
└─────────────────────────────────────────────────────┼───────────────┘
                                                      │ OTLP gRPC
                                                      ▼
                                          ┌───────────────────────┐
                                          │  OTel Collector       │
                                          │  :4317 (gRPC)         │
                                          │  :4318 (HTTP)         │
                                          └───────────┬───────────┘
                                                      │
                                                      ▼
                                          ┌───────────────────────┐
                                          │  ClickHouse           │
                                          │  :9000 (native)       │
                                          │  otel_traces table    │
                                          └───────────┬───────────┘
                                                      │
                                          ┌───────────▼───────────┐
                                          │  TraceCtrl Engine     │
                                          │  :8000 (FastAPI)      │
                                          │  Pipeline every 60s:  │
                                          │  spans → inventory    │
                                          │       → topology      │
                                          │       → attack graph  │
                                          │       → risk scoring  │
                                          │       → watermark     │
                                          └───────────┬───────────┘
                                                      │
                                          ┌───────────▼───────────┐
                                          │  TraceCtrl Dashboard  │
                                          │  :3000 (React)        │
                                          │  Topology, Sessions   │
                                          │  Agents, Risk, Attacks│
                                          └───────────────────────┘
```

## Quick Start

### Prerequisites

- **Docker** and **Docker Compose** (v2)
- **Python 3.10+** (for the SDK in your agent)
- **Node.js 20+** (only if developing the dashboard)

### Option A: TUI Setup (Recommended for First Time)

```bash
git clone https://github.com/cloudsineai/tracectrl.git
cd tracectrl
pip install textual rich
python setup/tui.py
```

The TUI wizard walks you through configuration, writes your `.env` file, and launches the stack.

### Option B: Manual Setup

```bash
git clone https://github.com/cloudsineai/tracectrl.git
cd tracectrl

# 1. Copy environment config
cp .env.example .env

# 2. Start the full stack (ClickHouse, OTel Collector, Engine, Dashboard)
docker compose up -d

# 3. Verify everything is running
docker compose ps
curl http://localhost:8000/api/v1/health
# → {"status":"ok","version":"0.1.0"}
```

### Option C: Development Mode (Hot Reload)

```bash
# Start with hot reload for engine and UI
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Or use the Makefile shortcut
make dev
```

In dev mode:
- Engine auto-reloads on Python file changes (port 8000)
- UI runs Vite dev server with HMR (port 5173 instead of 3000)

---

## Services & Ports

| Service | Port | Purpose |
|---------|------|---------|
| ClickHouse | `9000` (native), `8123` (HTTP) | Span storage, agent inventory, topology |
| OTel Collector | `4317` (gRPC), `4318` (HTTP) | Receives spans from SDK, exports to ClickHouse |
| TraceCtrl Engine | `8000` | REST API, pipeline scheduler |
| TraceCtrl Dashboard | `3000` | Topology, Sessions, Agents, Risk, Attack Paths |

---

## Instrumenting Your Agent

### Step 1: Install the SDK

```bash
# Core SDK (required)
pip install -e ./sdk/tracectrl

# Install the instrumentor for your framework
pip install -e ./sdk/tracectrl-instrumentation-langchain    # LangChain / LangGraph
pip install -e ./sdk/tracectrl-instrumentation-crewai       # CrewAI
pip install -e ./sdk/tracectrl-instrumentation-agno         # Agno
pip install -e ./sdk/tracectrl-instrumentation-google-adk   # Google ADK
pip install -e ./sdk/tracectrl-instrumentation-strands      # AWS Strands
```

### Step 2: Add 3 Lines to Your Agent

Add these lines **before** any framework imports:

```python
import tracectrl

tracectrl.configure(
    service_name="my-agent-service",
    endpoint="http://localhost:4317",
)

# Pick ONE — match your framework
from tracectrl.instrumentation.langchain import LangChainInstrumentor
LangChainInstrumentor().instrument()
```

### Step 3: Run Your Agent Normally

```python
# Everything below is your existing code — no changes needed
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor

llm = ChatOpenAI(model="gpt-4o")
# ... define tools, prompt, agent
agent_executor.invoke({"input": "Summarize my latest emails"})
```

Every LLM call, tool invocation, and chain execution is now captured as OpenTelemetry spans enriched with TraceCtrl security attributes.

### Framework-Specific Examples

<details>
<summary><b>CrewAI</b></summary>

```python
import tracectrl
tracectrl.configure(service_name="my-crew", endpoint="http://localhost:4317")

from tracectrl.instrumentation.crewai import CrewAIInstrumentor
CrewAIInstrumentor().instrument()

# Your CrewAI code
from crewai import Agent, Task, Crew
researcher = Agent(role="Researcher", goal="Find data", ...)
crew = Crew(agents=[researcher], tasks=[...])
crew.kickoff()
```
</details>

<details>
<summary><b>Agno</b></summary>

```python
import tracectrl
tracectrl.configure(service_name="my-agno-agent", endpoint="http://localhost:4317")

from tracectrl.instrumentation.agno import AgnoInstrumentor
AgnoInstrumentor().instrument()

# Your Agno code
from agno.agent import Agent
agent = Agent(model="gpt-4o", tools=[...])
agent.run("Analyze this document")
```
</details>

<details>
<summary><b>Google ADK</b></summary>

```python
import tracectrl
tracectrl.configure(service_name="my-adk-agent", endpoint="http://localhost:4317")

from tracectrl.instrumentation.google_adk import ADKInstrumentor
ADKInstrumentor().instrument()

# Your Google ADK code
from google.adk import Agent
agent = Agent(model="gemini-2.0-flash", tools=[...])
agent.run("Plan my trip")
```
</details>

<details>
<summary><b>AWS Strands</b></summary>

```python
import tracectrl
tracectrl.configure(service_name="my-strands-agent", endpoint="http://localhost:4317")

from tracectrl.instrumentation.strands import StrandsInstrumentor
StrandsInstrumentor().instrument()

# Your Strands code
from strands import Agent
agent = Agent(model="claude-sonnet-4-20250514")
agent("Summarize this report")
```
</details>

---

## Verifying the Data Flow

After running your instrumented agent, wait ~60 seconds for the pipeline to process, then:

### 1. Check Spans in ClickHouse

```bash
# Count total spans
docker exec -it $(docker compose ps -q clickhouse) clickhouse-client \
  --query "SELECT count() FROM tracectrl.otel_traces"

# See TraceCtrl attributes extracted from spans
docker exec -it $(docker compose ps -q clickhouse) clickhouse-client \
  --query "SELECT
    SpanAttributes['tracectrl.agent.id'] AS agent_id,
    SpanAttributes['tracectrl.agent.name'] AS agent_name,
    SpanAttributes['tracectrl.tool.category'] AS tool_category,
    SpanName
  FROM tracectrl.otel_traces
  WHERE SpanAttributes['tracectrl.agent.id'] != ''
  LIMIT 20
  FORMAT Pretty"
```

### 2. Check the Agent Inventory

```bash
docker exec -it $(docker compose ps -q clickhouse) clickhouse-client \
  --query "SELECT agent_id, name, framework, model, tools_observed, observation_count, maturity
  FROM tracectrl.agent_inventory FINAL
  FORMAT Pretty"
```

### 3. Check Topology Edges

```bash
# Agent-to-tool connections
docker exec -it $(docker compose ps -q clickhouse) clickhouse-client \
  --query "SELECT agent_id, tool_name, tool_category, call_count
  FROM tracectrl.topology_tool_edges FINAL
  FORMAT Pretty"

# Agent-to-agent connections (if using multi-agent)
docker exec -it $(docker compose ps -q clickhouse) clickhouse-client \
  --query "SELECT caller_agent_id, callee_agent_id, observation_count, confidence
  FROM tracectrl.topology_agent_edges FINAL
  FORMAT Pretty"
```

### 4. Query the Engine API

```bash
# Full topology graph (used by the dashboard)
curl http://localhost:8000/api/v1/topology/graph | python -m json.tool

# Agent inventory list
curl http://localhost:8000/api/v1/agents | python -m json.tool

# Risk summary (system-level score)
curl http://localhost:8000/api/v1/risk/summary | python -m json.tool

# Attack paths (ranked vulnerability chains)
curl http://localhost:8000/api/v1/risk/attack-paths | python -m json.tool

# Per-agent risk scores
curl http://localhost:8000/api/v1/risk/agent-scores | python -m json.tool
```

### 5. View the Dashboard

Open [http://localhost:3000](http://localhost:3000) in your browser.

- **Topology Graph** — Interactive agent/tool graph with dagre layout. Toggle between developer view (data flow) and attacker view (attack surface overlay with risk-colored edges).
- **Sessions** — Trace explorer with sortable session list, inline span tree expansion, and waterfall timeline with phase overlay and replay scrubber.
- **Agents** — Agent inventory with expandable tool details showing call counts, error rates, and tool categories.
- **Risk Dashboard** — System-level risk score, per-agent risk table with CVSS-based scoring, and risk trend indicators.
- **Attack Paths** — Ranked vulnerability chains with step-by-step expansion showing the rule, affected agents, and blast radius.

---

## SDK Features

### Security Enrichment

The `TraceCtrlSpanProcessor` automatically enriches every span with security-relevant attributes:

| Attribute | Source | Purpose |
|-----------|--------|---------|
| `tracectrl.agent.id` | Agent config | Unique agent identity |
| `tracectrl.agent.name` | Agent config | Human-readable name |
| `tracectrl.agent.framework` | Instrumentor | Framework detection |
| `tracectrl.agent.role` | Agent config | Agent role/purpose |
| `tracectrl.session_id` | Context var | Session correlation |
| `tracectrl.tool.category` | Inferred | Risk classification |
| `tracectrl.input.source` | Inferred | Input provenance |
| `tracectrl.caller.agent_id` | Context | Multi-agent tracing |
| `tracectrl.system_prompt_hash` | Computed | Prompt drift detection |

### Tool Category Inference

Every tool call is automatically classified into a risk category:

| Category | Matches | Risk Signal |
|----------|---------|-------------|
| `code_execution` | exec, python, bash, shell, eval | High — arbitrary code |
| `email` | send_email, smtp | High — data exfiltration |
| `external_api` | http, fetch, curl, scrape, web | Medium — network access |
| `file_system` | write_file, delete_file, rm | Medium — filesystem mutation |
| `memory_write` | vector, embed, upsert, index | Medium — memory poisoning |
| `memory_read` | search, query, retrieve, recall | Low — information access |
| `human_interaction` | approval, confirm, ask_user | Low — HITL safety |
| `internal_api` | _(default)_ | Low — internal function |

### Session Management

```python
from tracectrl.session import new_session, current_session_id, set_session_id

# Automatic — SDK generates a session ID per thread/async context
sid = new_session()

# Manual — override with your own session ID
set_session_id("user-session-abc123")

# Read current
print(current_session_id())
```

### Cross-Process Context Propagation

For multi-service agent architectures (HTTP-based):

```python
from tracectrl.context import inject_trace_headers, extract_trace_headers

# Service A: inject trace context into outgoing request
headers = {}
inject_trace_headers(headers)
requests.post("http://service-b/api", headers=headers)

# Service B: extract trace context from incoming request
extract_trace_headers(request.headers)
# All subsequent spans are correlated to the same trace
```

---

## MCP Proxy Server

The MCP proxy transparently intercepts tool calls from IDE agents (Cursor, Claude Code) and emits OpenTelemetry spans to TraceCtrl. No changes to your agent or MCP server configuration required — just insert the proxy in front of your downstream servers.

```bash
# Install
pip install -e ./sdk/tracectrl-mcp

# Run — list the downstream MCP servers to proxy
TRACECTRL_DOWNSTREAM=filesystem,github tracectrl-mcp
```

The proxy captures tool call names, arguments, latency, and results as spans with full `input.source` classification, then forwards every call to the real downstream server unchanged.

---

## Engine API Reference

All endpoints are prefixed with `/api/v1`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check — returns `{"status": "ok"}` |
| `GET` | `/topology/graph` | Full topology graph: `{nodes: [...], edges: [...]}` |
| `GET` | `/topology/agents/{agent_id}` | Single agent detail |
| `GET` | `/sessions` | Session list with trace metadata |
| `GET` | `/sessions/{trace_id}/spans` | All spans for a trace (span tree) |
| `GET` | `/agents` | Agent inventory with tools, maturity, observation counts |
| `GET` | `/agents/{id}/tools` | Tools for a specific agent with call counts and error rates |
| `GET` | `/risk/agents` | All agents with maturity and observation counts |
| `GET` | `/risk/summary` | System-level risk score and aggregate metrics |
| `GET` | `/risk/attack-paths` | Ranked attack paths with step details and blast radius |
| `GET` | `/risk/agent-scores` | Per-agent CVSS-based risk scores |

### Pipeline

The engine runs a background pipeline every `PIPELINE_INTERVAL_SECONDS` (default: 60):

1. **Fetch** — Read new spans from `otel_traces` since the last watermark
2. **Inventory** — Upsert agent records with cumulative observation counts
3. **Topology** — Upsert agent-to-agent and agent-to-tool edges
4. **Attack Graph** — Run TAGAAI rules (prompt injection, excessive agency, data leakage) and build vulnerability chains
5. **Risk Scoring** — Compute per-agent and system-level risk scores using CVSS-based formula
6. **Watermark** — Advance the watermark timestamp (only on success)

The watermark is **not advanced** on empty results or failures, ensuring no data is skipped.

---

## Project Structure

```
tracectrl/
├── sdk/                                    # Component 1: Python SDK
│   ├── tracectrl/                          # pip install tracectrl (core)
│   │   └── src/tracectrl/
│   │       ├── config.py                   # configure() — TracerProvider setup
│   │       ├── processor.py                # TraceCtrlSpanProcessor
│   │       ├── inference.py                # Tool category classification
│   │       ├── session.py                  # Session ID via contextvars
│   │       ├── schema.py                   # Attribute name constants
│   │       └── context.py                  # W3C traceparent helpers
│   ├── tracectrl-instrumentation-langchain/
│   ├── tracectrl-instrumentation-crewai/
│   ├── tracectrl-instrumentation-agno/
│   ├── tracectrl-instrumentation-google-adk/
│   └── tracectrl-instrumentation-strands/
│
├── engine/                                 # Component 2: Intelligence Engine
│   ├── main.py                             # FastAPI app
│   ├── scheduler.py                        # APScheduler pipeline runner
│   ├── pipeline/runner.py                  # fetch → inventory → topology
│   ├── db/                                 # ClickHouse data layer
│   └── api/routes/                         # REST API endpoints
│
├── ui/                                     # Component 3: React Dashboard
│   └── src/
│       ├── styles/globals.css              # Brand design system
│       ├── pages/                          # Topology, Sessions, Risk, Attacks
│       └── components/                     # GraphCanvas, SidebarPanel
│
├── config/
│   ├── otel-collector.yaml                 # OTel Collector pipeline config
│   └── schema.sql                          # ClickHouse table definitions
│
├── docker-compose.yml                      # Production stack (4 services)
├── docker-compose.dev.yml                  # Dev overrides (hot reload)
├── Makefile                                # setup, dev, test, lint, build, clean
└── setup/tui.py                            # First-time setup TUI wizard
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRACECTRL_ENDPOINT` | `http://localhost:4317` | OTel Collector gRPC endpoint |
| `TRACECTRL_SERVICE_NAME` | `tracectrl-agent` | Service name for spans |
| `TRACECTRL_FAIL_SILENTLY` | `true` | Don't crash the agent if tracing fails |
| `CLICKHOUSE_HOST` | `localhost` | ClickHouse host (use `clickhouse` in Docker) |
| `CLICKHOUSE_PORT` | `9000` | ClickHouse native protocol port |
| `CLICKHOUSE_DB` | `tracectrl` | ClickHouse database name |
| `PIPELINE_INTERVAL_SECONDS` | `60` | How often the pipeline processes new spans |
| `VITE_ENGINE_URL` | `http://localhost:8000` | Engine API URL (baked into UI at build time) |

---

## Development

### Local Setup (Outside Docker)

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install everything
make setup

# Install instrumentors (for testing)
pip install -e ./sdk/tracectrl-instrumentation-langchain
pip install -e ./sdk/tracectrl-instrumentation-crewai
pip install -e ./sdk/tracectrl-instrumentation-agno
pip install -e ./sdk/tracectrl-instrumentation-google-adk
pip install -e ./sdk/tracectrl-instrumentation-strands
```

### Running Tests

```bash
make test     # Run pytest
make lint     # Run ruff linter
```

### Makefile Targets

| Target | Description |
|--------|-------------|
| `make setup` | Install SDK, engine deps, and test tools |
| `make dev` | Start full stack with hot reload |
| `make test` | Run pytest test suite |
| `make lint` | Run ruff linter on all Python code |
| `make build` | Build Docker images |
| `make tui` | Launch the setup TUI wizard |
| `make clean` | Tear down containers, remove caches |

---

## Troubleshooting

### No spans appearing in ClickHouse

1. **Is the OTel Collector running?** `docker compose ps` — check otel-collector is up
2. **Is the SDK pointing to the right endpoint?** The default `http://localhost:4317` works when your agent runs on the host machine. If your agent runs inside Docker, use `http://otel-collector:4317`
3. **Check collector logs:** `docker compose logs otel-collector`
4. **Verify spans are arriving:** `docker compose logs otel-collector 2>&1 | grep "TracesExporter"`

### Agent inventory is empty after running agent

The pipeline runs every 60 seconds by default. Wait at least one interval, then check:
```bash
docker compose logs tracectrl-engine 2>&1 | grep "Pipeline run"
```

If you see "No new spans. Skipping pipeline run." — the spans haven't arrived yet. Check the OTel Collector logs.

### Dashboard shows "Loading..." with no data

1. **Is the engine healthy?** `curl http://localhost:8000/api/v1/health`
2. **Does the API return data?** `curl http://localhost:8000/api/v1/topology/graph`
3. **CORS issue?** Check browser console. The engine allows all origins by default.

### ClickHouse shows duplicate rows

This is expected with ReplacingMergeTree — duplicates are deduplicated during background merges. Always query with `FINAL` for correct results:
```sql
SELECT * FROM tracectrl.agent_inventory FINAL
```

---

## Roadmap

### Sprint 1 — End-to-End Skeleton
- [x] Python SDK with 5 framework instrumentors
- [x] OTel Collector → ClickHouse pipeline
- [x] Intelligence Engine with agent inventory and topology
- [x] Dashboard with interactive topology graph
- [x] Docker Compose one-command setup
- [x] TUI first-time wizard

### Sprint 2 (Current) — Risk Engine & Attack Graphs
- [x] TAGAAI attack graph engine with 3 detection rules (prompt injection ASI-01, excessive agency ASI-02, data leakage ASI-01+ASI-02)
- [x] CVSS-based risk scoring (per-agent and system-level)
- [x] MCP proxy server for IDE agent tracing (Cursor, Claude Code)
- [x] Full span schema with `input.source` classification (user/agent/external/memory)
- [x] 5 dashboard pages: Topology (with attacker view toggle), Sessions, Agents, Risk Dashboard, Attack Paths
- [x] Risk and attack path API endpoints

### Sprint 3 — Validation & Polish
- [ ] Integration test harnesses for 5 TAGAAI attack scenarios
- [ ] Detection threshold tuning
- [ ] Performance benchmarks (SDK overhead < 5ms/LLM call)
- [ ] Cross-process context propagation validation
- [ ] Dashboard polish: loading states, error handling, empty states

---

## License

Proprietary — CloudsineAI Pte. Ltd. All rights reserved.

Contact: [info@tracectrl.ai](mailto:info@tracectrl.ai)
