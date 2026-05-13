# TraceCtrl

**Security Observability & Control for Agentic AI**

[![License: BUSL-1.1](https://img.shields.io/badge/License-BUSL--1.1-blue.svg)](LICENSE)
[![SDK License: Apache-2.0](https://img.shields.io/badge/SDK-Apache--2.0-green.svg)](sdk/tracectrl/LICENSE)

TraceCtrl gives security teams and developers complete visibility into every agent action, tool call, and data access — with runtime protection and attack graph risk scoring powered by TAGAAI.

[Website](https://tracectrl.ai) | [Documentation](https://docs.tracectrl.ai) | [Contact](mailto:info@tracectrl.ai)

---

## Install

| Package | Version | Monthly Downloads |
|---------|---------|-------------------|
| `tracectrl` | [![PyPI](https://img.shields.io/pypi/v/tracectrl?color=blue)](https://pypi.org/project/tracectrl/) | [![Downloads](https://img.shields.io/pypi/dm/tracectrl?color=blue)](https://pypistats.org/packages/tracectrl) |
| `tracectrl-scanner` | [![PyPI](https://img.shields.io/pypi/v/tracectrl-scanner?color=blue)](https://pypi.org/project/tracectrl-scanner/) | [![Downloads](https://img.shields.io/pypi/dm/tracectrl-scanner?color=blue)](https://pypistats.org/packages/tracectrl-scanner) |
| `tracectrl-instrumentation-agno` | [![PyPI](https://img.shields.io/pypi/v/tracectrl-instrumentation-agno?color=blue)](https://pypi.org/project/tracectrl-instrumentation-agno/) | [![Downloads](https://img.shields.io/pypi/dm/tracectrl-instrumentation-agno?color=blue)](https://pypistats.org/packages/tracectrl-instrumentation-agno) |
| `tracectrl-instrumentation-strands` | [![PyPI](https://img.shields.io/pypi/v/tracectrl-instrumentation-strands?color=blue)](https://pypi.org/project/tracectrl-instrumentation-strands/) | [![Downloads](https://img.shields.io/pypi/dm/tracectrl-instrumentation-strands?color=blue)](https://pypistats.org/packages/tracectrl-instrumentation-strands) |

**Docker images (GHCR)**

[![Engine](https://img.shields.io/badge/ghcr.io-tracectrl--engine-blue?logo=docker)](https://ghcr.io/tracectrl/tracectrl-engine)
[![UI](https://img.shields.io/badge/ghcr.io-tracectrl--ui-blue?logo=docker)](https://ghcr.io/tracectrl/tracectrl-ui)

---

## Features

- **TAGAAI Attack Graph Engine** — Automated vulnerability detection with built-in rules for prompt injection, excessive agency, and data leakage. CVSS-based risk scoring combining base severity, exploitability, and blast radius.
- **TraceCtrl Guards** — Built-in LLM-judge guardrails plus optional integration with Cloudsine GenAI Protector Plus (prompt injection, PII, content moderation, vector similarity, system-prompt leakage). Configured from the dashboard, instrumented from the SDK via `tracectrl.guard()`.
- **MCP Proxy Server** — Transparent proxy for IDE agent tracing (Cursor, Claude Code). Captures every tool call made through MCP-compatible agents without code changes.
- **Security-Enriched Spans** — OpenTelemetry spans with `input.source` classification, memory write provenance, prompt drift detection, and tool risk categorization.
- **Dashboard** — Topology (developer + attacker view), Sessions (trace explorer), Agents (inventory), Guardrails (registry + invocations), Risk Dashboard, and Attack Paths (ranked vulnerability chains).
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
make start
```

`make start` pulls the latest engine and UI images from GHCR and starts the full stack.

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
pip install tracectrl
python examples/demo_agent.py
```

Open [http://localhost:3000/sessions](http://localhost:3000/sessions) — you should see a "Demo Agent" trace with 4 spans (1 agent, 2 LLM, 1 tool).

To scan an OpenClaw installation for security issues:

```bash
pip install tracectrl-scanner
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
