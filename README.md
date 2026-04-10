# TraceCtrl

**Security Observability & Control for Agentic AI**

[![License: BUSL-1.1](https://img.shields.io/badge/License-BUSL--1.1-blue.svg)](LICENSE)
[![SDK License: Apache-2.0](https://img.shields.io/badge/SDK-Apache--2.0-green.svg)](sdk/tracectrl/LICENSE)

TraceCtrl gives security teams and developers complete visibility into every agent action, tool call, and data access — with runtime protection and attack graph risk scoring powered by TAGAAI.

[Website](https://tracectrl.ai) | [Documentation](https://docs.tracectrl.ai) | [Contact](mailto:info@tracectrl.ai)

---

## Features

- **TAGAAI Attack Graph Engine** — Automated vulnerability detection with built-in rules for prompt injection, excessive agency, and data leakage. CVSS-based risk scoring combining base severity, exploitability, and blast radius.
- **MCP Proxy Server** — Transparent proxy for IDE agent tracing (Cursor, Claude Code). Captures every tool call made through MCP-compatible agents without code changes.
- **Security-Enriched Spans** — OpenTelemetry spans with `input.source` classification, memory write provenance, prompt drift detection, and tool risk categorization.
- **Dashboard** — Topology (developer + attacker view), Sessions (trace explorer), Agents (inventory), Risk Dashboard, and Attack Paths (ranked vulnerability chains).
- **Framework Support** — Agno and AWS Strands (stable), LangChain, CrewAI, Google ADK, and OpenClaw (beta) — each requiring only 3 lines of code.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Your Agent (Python)                                                │
│  ┌───────────────┐  ┌─────────────────────┐  ┌──────────────────┐   │
│  │ tracectrl SDK │→ │ Framework           | →│ TraceCtrl        │   │
│  │ configure()   │  │ Instrumentor (OI)   |  │ SpanProcessor    |   │
│  └───────────────┘  └─────────────────────┘  └──────┬───────────┘   │
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
                                          │  otel_traces table    │
                                          └───────────┬───────────┘
                                                      │
                                          ┌───────────▼───────────┐
                                          │  TraceCtrl Engine     │
                                          │  :8000 (FastAPI)      │
                                          │  Pipeline: spans →    │
                                          │  inventory → topology │
                                          │  → attack graph →     │
                                          │  risk scoring         │
                                          └───────────┬───────────┘
                                                      │
                                          ┌───────────▼───────────┐
                                          │  TraceCtrl Dashboard  │
                                          │  :3000 (React)        │
                                          └───────────────────────┘
```

---

## Quick Start

### Prerequisites

- **Docker** and **Docker Compose** v2
- **Python 3.10+**

### Setup

```bash
git clone https://github.com/tracectrl/tracectrl.git
cd tracectrl
cp .env.example .env
docker compose up -d
```

Verify the stack is running:

```bash
curl http://localhost:8000/api/v1/health
# → {"status":"ok","version":"0.1.0"}
```

The dashboard is available at [http://localhost:3000](http://localhost:3000).

For detailed setup options including the TUI wizard and development mode, see the [Quickstart Guide](https://docs.tracectrl.ai/quickstart).

### Try It (30 seconds)

After the stack is running, send test spans with the included demo agent:

```bash
pip install -e ./sdk/tracectrl
python examples/demo_agent.py
```

Open [http://localhost:3000/sessions](http://localhost:3000/sessions) — you should see a "Demo Agent" trace with 4 spans (1 agent, 2 LLM, 1 tool).

To scan an OpenClaw installation for security issues:

```bash
pip install -e ./scanner
tracectrl scan ~/.openclaw/
```

---

## Instrument Your Agent

```bash
pip install tracectrl
pip install tracectrl-instrumentation-langchain  # or your framework
```

Add these lines **before** any framework imports:

```python
import tracectrl

tracectrl.configure(
    service_name="my-agent-service",
    endpoint="http://localhost:4317",
)

from tracectrl.instrumentation.langchain import LangChainInstrumentor
LangChainInstrumentor().instrument()

# Your existing agent code — no changes needed
```

Every LLM call, tool invocation, and chain execution is captured as OpenTelemetry spans enriched with security attributes.

### Supported Frameworks

| Framework | Package |
|-----------|---------|
| LangChain / LangGraph | `tracectrl-instrumentation-langchain` |
| CrewAI | `tracectrl-instrumentation-crewai` |
| Agno | `tracectrl-instrumentation-agno` |
| Google ADK | `tracectrl-instrumentation-google-adk` |
| AWS Strands | `tracectrl-instrumentation-strands` |

See the [framework integration guides](https://docs.tracectrl.ai/instrumentors/langchain) for detailed examples.

---

## Services & Ports

| Service | Port | Purpose |
|---------|------|---------|
| ClickHouse | `9000`, `8123` | Span storage |
| OTel Collector | `4317` (gRPC), `4318` (HTTP) | Span ingestion |
| TraceCtrl Engine | `8000` | REST API and pipeline |
| TraceCtrl Dashboard | `3000` | Visualization |

---

## Documentation

Full documentation is available at [docs.tracectrl.ai](https://docs.tracectrl.ai):

- [Quickstart](https://docs.tracectrl.ai/quickstart) — Get running in 5 minutes
- [SDK Installation](https://docs.tracectrl.ai/sdk/installation) — Install and configure the SDK
- [Architecture](https://docs.tracectrl.ai/architecture) — How data flows through the system
- [Security Enrichment](https://docs.tracectrl.ai/security/enrichment) — Span attributes and tool classification
- [API Reference](https://docs.tracectrl.ai/api-reference/overview) — Engine REST API

---

## Contributing

We welcome contributions. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request. All contributors must sign our [CLA](CLA.md).

---

## License

TraceCtrl uses a split licensing model:

- **SDK packages** (`sdk/`) — [Apache License 2.0](sdk/tracectrl/LICENSE). Free to use, modify, and embed in your applications.
- **Platform** (engine, UI, config, setup) — [Business Source License 1.1](LICENSE). Free for non-competitive use. Converts to Apache 2.0 after four years per version.

See [LICENSE](LICENSE) for full terms. For commercial licensing, contact [info@tracectrl.ai](mailto:info@tracectrl.ai).

TraceCtrl is wholly owned by Cloudsine Pte Ltd.
