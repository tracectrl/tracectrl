# TraceCtrl SDK — Feature Specification & Implementation Plan

**Product:** TraceCtrl by CloudsineAI
**Component:** Component 1 — SDK & Instrumentation Layer
**Version:** MVP 2.0
**Status:** Ready for implementation
**Last updated:** March 2026

---

## TL;DR — Read This First

**What this is:** A Python SDK that instruments agentic AI frameworks to emit security-enriched OpenTelemetry spans. These spans feed the TraceCtrl Risk Intelligence Engine to detect OWASP Top 10 for Agentic Applications threats (ASI01–ASI10) at runtime.

**How it works:** Each TraceCtrl instrumentor wraps the corresponding [OpenInference](https://github.com/Arize-ai/openinference) framework instrumentor (which handles all the framework monkey-patching) and registers a TraceCtrl `SpanProcessor` on the same `TracerProvider`. The SpanProcessor intercepts every span as it flows through and enriches it with security-critical `tracectrl.*` attributes — tool category, input source origin, system prompt hash, memory write provenance — that the Risk Engine needs but OpenInference doesn't emit.

```
OpenInference Instrumentor   ← handles framework patching (LangChain, CrewAI, etc.)
        ↓  emits spans with standard OI attributes (input.value, tool.name, llm.model_name, ...)
TraceCtrl SpanProcessor      ← enriches spans with tracectrl.* security attributes
        ↓
OTel Collector → ClickHouse  ← Component 2
```

**One-call setup for the developer:**
```python
from tracectrl.instrumentation.langchain import LangChainInstrumentor
LangChainInstrumentor().instrument()  # wraps OI instrumentor + registers SpanProcessor
```

**Supported frameworks:** LangChain/LangGraph, Google ADK, CrewAI, AWS Strands, Agno, MCP (Cursor / Claude Code).

**Output:** OTLP spans over gRPC to an OTel Collector. Zero changes to application agent code required.

**Build scope:** Component 1 of 4 in TraceCtrl MVP 2.0. Sprint 3 ships core + LangChain + ADK + MCP. Sprint 4 completes CrewAI + Strands + Agno + cross-process context.

---

## Context for the Implementer

TraceCtrl is an agentic AI security observability platform. Its job is to collect runtime telemetry from AI agent frameworks and pipe it to a risk intelligence engine that detects threats mapped to the OWASP Top 10 for Agentic Applications (ASI01–ASI10).

The SDK is the data collection layer — Component 1 of 4. It must be:
- **Zero-friction to install**: one pip install, one instrument() call
- **Framework-native**: wraps existing OpenInference instrumentation where it exists, builds new where it doesn't
- **Schema-rich**: every span must carry the fields the Risk Engine needs (see Span Schema section)
- **Interoperable**: emits standard OTLP so the OTel Collector (Component 2) can receive it without SDK-specific logic

This spec is the source of truth for what to build. The acceptance criteria are testable. Build in phase order.

---

## 1. Problem Statement

Engineering teams deploying agentic AI systems (LangChain, CrewAI, Google ADK, AWS Strands, Agno) have no runtime visibility into whether their agents are behaving securely. Existing observability tools (Datadog, LangSmith, Arize) capture performance telemetry but do not emit the security-relevant fields needed to detect prompt injection, privilege abuse, cascade failures, or memory poisoning at runtime.

The TraceCtrl SDK solves this by producing semantically enriched OTLP spans from agentic framework events — spans that carry agent identity, tool call context, inter-agent communication metadata, and memory operation provenance. These spans feed the Risk Intelligence Engine (Component 3), which maps runtime behaviour to OWASP threat categories.

**Who experiences this problem:** Platform engineers and AI security engineers at companies deploying production multi-agent systems.

**Cost of not solving it:** Blind production deployments. The five attack scenarios documented in the TraceCtrl MVP 2.0 document (email assistant goal hijack, expense approval identity spoofing, IDE agent RCE, RAG memory poisoning, MCP supply chain override) are all undetectable without runtime span data.

---

## 2. Goals

1. A developer can instrument any supported framework in under 5 minutes with 2 lines of code and receive spans in the TraceCtrl dashboard.
2. Every span carries the full set of Risk Engine required fields (see Span Schema) — no post-processing or enrichment needed downstream.
3. The SDK adds less than 5ms overhead per LLM call and less than 1ms per tool call.
4. Multi-agent traces are correctly stitched — spans from Agent A calling Agent B share the same `trace_id` and the child span's `parent_span_id` points to the correct parent.
5. The SDK ships instrumentation for all five target frameworks (ADK, LangChain/LangGraph, CrewAI, Strands, Agno) plus the MCP server for Cursor/Claude Code IDE integration by end of Sprint 4.

---

## 3. Non-Goals (MVP 2.0)

- **No agent policy declaration in the SDK.** The SDK collects and emits. Policy evaluation happens in Component 3. Do not add rule engine logic to the SDK.
- **No blocking/guardrail enforcement.** The SDK is read-only from the agent's perspective. It instruments but never intercepts or modifies agent behaviour. That is Component 4 (TraceCtrl Guard), Sprint 5+.
- **No UI or dashboard.** The SDK emits OTLP. Dashboard is Component 4.
- **No automatic PII redaction.** Emit full span content. PII handling is a pipeline-level concern (Component 2). Do not truncate or mask fields in the SDK — the Risk Engine needs the full content.
- **No support for non-Python frameworks in MVP.** JavaScript/TypeScript agentic frameworks (Vercel AI SDK, LangChain.js) are Sprint 5+.

---

## 4. User Stories

**P0 — Must have for launch**

- As a backend engineer, I want to run `pip install tracectrl tracectrl-instrumentation-langchain` and call `LangChainInstrumentor().instrument()` so that all LangChain/LangGraph agent runs are traced without modifying my agent code.
- As a backend engineer, I want to run `pip install tracectrl tracectrl-instrumentation-google-adk` and call `ADKInstrumentor().instrument()` so that all Google ADK agent runs emit spans to my OTel Collector.
- As a backend engineer, I want spans to include the agent's name, session ID, tool name, input/output content, and model identifier so that the Risk Engine has the fields it needs for detection.
- As a backend engineer, I want multi-agent traces to be correctly stitched with shared `trace_id` and correct `parent_span_id` so that the Risk Engine can reconstruct full causal chains.
- As a security engineer, I want memory read and write events (vector store operations) to emit spans tagged with the originating trace's provenance (internal vs external input source) so that the Risk Engine can run write provenance tracking for ASI06.
- As a security engineer, I want inter-agent communication events to emit spans with both the calling agent's identity and the receiving agent's identity so that topology violations can be detected.

**P1 — Important, ship in Sprint 4**

- As a Cursor user, I want to install the TraceCtrl MCP server and have all MCP tool calls automatically traced so that IDE-level agent activity is visible in the dashboard.
- As a Claude Code user, I want to add `tracectrl` as an MCP server in my `.clauderc` so that all Claude Code agent runs emit security telemetry.
- As a platform engineer, I want to configure the OTLP endpoint, service name, and batch export interval via environment variables so that I do not need to change code between environments.
- As a platform engineer, I want the SDK to fail silently (emit a warning log, continue running) if the OTel Collector is unreachable so that a telemetry outage never causes an agent outage.

**P2 — Future**

- As an enterprise security engineer, I want to declare agent policy (allowed tools, permitted recipients, max privilege scope) in the SDK config so that the Risk Engine has policy context for gap scoring.
- As a platform engineer, I want the SDK to support OpenTelemetry Sampling so that high-volume deployments can reduce telemetry costs by sampling low-risk traces.

---

## 5. Package Structure

```
tracectrl/                          # Core package — pip install tracectrl
├── __init__.py
├── exporter.py                     # OTLP exporter config + batch processor
├── context.py                      # Trace context propagation helpers
├── schema.py                       # TraceCtrl span attribute constants
├── session.py                      # Session ID generation + management
└── agent_registry.py               # In-process agent inventory (name → ID mapping)

tracectrl-instrumentation-langchain/   # pip install tracectrl-instrumentation-langchain
├── tracectrl/instrumentation/langchain/
│   ├── __init__.py
│   ├── instrumentor.py             # LangChainInstrumentor class
│   ├── callbacks.py                # LangChain callback handler
│   └── patch.py                   # Monkey-patches for LangGraph state machine events

tracectrl-instrumentation-google-adk/
├── tracectrl/instrumentation/google_adk/
│   ├── __init__.py
│   ├── instrumentor.py             # ADKInstrumentor class
│   └── patch.py                   # ADK event hooks

tracectrl-instrumentation-crewai/
├── tracectrl/instrumentation/crewai/
│   ├── __init__.py
│   ├── instrumentor.py             # CrewAIInstrumentor class
│   └── patch.py

tracectrl-instrumentation-strands/
├── tracectrl/instrumentation/strands/
│   ├── __init__.py
│   ├── instrumentor.py             # StrandsInstrumentor class
│   └── patch.py                   # OTel env var config for native OTel support

tracectrl-instrumentation-agno/
├── tracectrl/instrumentation/agno/
│   ├── __init__.py
│   ├── instrumentor.py             # AgnoInstrumentor class
│   └── patch.py

tracectrl-mcp/                      # pip install tracectrl-mcp
├── tracectrl/mcp/
│   ├── __init__.py
│   ├── server.py                   # MCP server entrypoint
│   ├── proxy.py                    # Tool call proxy — wraps every tool call with a span
│   └── schema_scanner.py           # Scans tool descriptors for instruction-like patterns (Tier 1)
```

---

## 6. Architecture: Building on OpenInference

### 6.1 Why OpenInference

[OpenInference](https://github.com/Arize-ai/openinference) (published by Arize AI) is the de facto semantic conventions standard and instrumentation library for LLM observability. It already ships working instrumentors for LangChain, CrewAI, and others — they handle the complex framework monkey-patching and emit spans with a well-defined attribute schema (`input.value`, `output.value`, `llm.model_name`, `tool.name`, etc.).

TraceCtrl does **not** rewrite this. Instead, it layers on top: OpenInference owns the framework integration, TraceCtrl owns the security enrichment.

### 6.2 Layering Model

```
┌─────────────────────────────────────────────────────────┐
│  Application Code  (LangChain agent, CrewAI crew, etc.) │
└────────────────────────────┬────────────────────────────┘
                             │ framework events
                             ▼
┌─────────────────────────────────────────────────────────┐
│  OpenInference Instrumentor                             │
│  (openinference-instrumentation-langchain, -crewai ...) │
│  • Monkey-patches framework internals                   │
│  • Emits spans: input.value, tool.name, llm.model_name  │
└────────────────────────────┬────────────────────────────┘
                             │ OTel spans (OI attributes)
                             ▼
┌─────────────────────────────────────────────────────────┐
│  TraceCtrl SpanProcessor                                │
│  (registered on the same TracerProvider)                │
│  • Reads OI attributes, derives security context        │
│  • Adds tracectrl.tool.category (from tool.name)        │
│  • Adds tracectrl.input.source (from span parent chain) │
│  • Adds tracectrl.system_prompt_hash (from llm.system)  │
│  • Adds tracectrl.memory.write_provenance               │
│  • Adds tracectrl.agent.*, tracectrl.session_id, etc.   │
└────────────────────────────┬────────────────────────────┘
                             │ enriched OTLP spans
                             ▼
              OTel Collector → ClickHouse  (Component 2)
```

### 6.3 What Each Layer Owns

| Responsibility | Owner |
|---|---|
| Framework monkey-patching (Chain, LLM, Tool hooks) | OpenInference instrumentor |
| Standard span attributes (`input.value`, `tool.name`, `llm.model_name`, `retrieval.documents`) | OpenInference instrumentor |
| `tracectrl.*` security attributes | TraceCtrl SpanProcessor |
| Session management (`tracectrl.session_id`) | TraceCtrl SpanProcessor |
| Tool category inference (`tracectrl.tool.category`) | TraceCtrl SpanProcessor |
| Input source classification (`tracectrl.input.source`) | TraceCtrl SpanProcessor |
| System prompt hashing (`tracectrl.system_prompt_hash`) | TraceCtrl SpanProcessor |
| Memory write provenance (`tracectrl.memory.write_provenance`) | TraceCtrl SpanProcessor |
| MCP proxy + schema scanner | TraceCtrl MCP server (no OI equivalent) |
| Cross-process trace context propagation | TraceCtrl context helpers (wraps W3C traceparent) |

### 6.4 What Each Instrumentor Actually Does

Each `FWInstrumentor().instrument()` call does exactly two things:

1. Calls the corresponding OpenInference instrumentor's `.instrument()` to activate framework patching
2. Registers a `TraceCtrlSpanProcessor` on the `TracerProvider`

```python
# Simplified internals of LangChainInstrumentor.instrument()
from openinference.instrumentation.langchain import LangChainInstrumentor as OILangChainInstrumentor
from tracectrl.processor import TraceCtrlSpanProcessor

class LangChainInstrumentor:
    def instrument(self, *, tracer_provider=None, skip_dep_check=False):
        tp = tracer_provider or trace.get_tracer_provider()
        # Step 1: activate OpenInference framework patching
        OILangChainInstrumentor().instrument(tracer_provider=tp, skip_dep_check=skip_dep_check)
        # Step 2: register TraceCtrl enrichment processor
        tp.add_span_processor(TraceCtrlSpanProcessor())
```

### 6.5 Frameworks Without an OpenInference Instrumentor

For frameworks where OpenInference does not publish an instrumentor:

- **MCP** — no OI equivalent; `tracectrl-mcp` is a fully custom transparent proxy server

All five agentic AI frameworks (LangChain, CrewAI, Google ADK, AWS Strands, Agno) have published OpenInference instrumentors and follow the identical wrap pattern.

---

## 7. Core SDK — `tracectrl` Package

### 7.1 Installation and Setup

```python
pip install tracectrl
```

### 7.2 Configuration

The SDK is configured entirely via environment variables. No config file required for basic use.

| Environment Variable | Default | Description |
|---|---|---|
| `TRACECTRL_ENDPOINT` | `http://localhost:4317` | OTLP gRPC endpoint for the OTel Collector |
| `TRACECTRL_HTTP_ENDPOINT` | `None` | OTLP HTTP endpoint (alternative to gRPC) |
| `TRACECTRL_SERVICE_NAME` | `tracectrl-agent` | Service name attached to all spans |
| `TRACECTRL_API_KEY` | `None` | Bearer token for authenticated endpoints |
| `TRACECTRL_BATCH_DELAY_MS` | `1000` | Max delay before flushing span batch |
| `TRACECTRL_MAX_BATCH_SIZE` | `512` | Max spans per batch |
| `TRACECTRL_FAIL_SILENTLY` | `true` | If true, exporter errors are logged, not raised |
| `TRACECTRL_SESSION_ID` | Auto-generated | Override session ID (useful for test fixtures) |

### 7.3 Programmatic Configuration (Optional)

```python
from tracectrl import configure

configure(
    endpoint="http://otel-collector:4317",
    service_name="my-agent-service",
    api_key="tc-key-abc123",
    fail_silently=True,
)
```

`configure()` must be called before any `Instrumentor().instrument()` call if used. If `configure()` is not called, environment variables are used. If neither is set, the SDK uses defaults and logs a warning.

### 7.4 Session Management

Every agent run is associated with a `session_id`. A session represents one end-to-end invocation of an agent or agent pipeline.

```python
from tracectrl.session import new_session, current_session_id

session_id = new_session()          # generates UUID4, stores in context var
current = current_session_id()      # retrieves from context var
```

The session ID is attached to every span as `tracectrl.session_id`. Instrumentors call `new_session()` automatically at the start of each agent run unless a session ID is already set in the context (allowing multi-agent chaining to share session IDs).

**Acceptance criteria:**
- [ ] All spans from a single agent run share the same `tracectrl.session_id`
- [ ] When Agent A calls Agent B, Agent B's spans share Agent A's `tracectrl.session_id`
- [ ] A new `tracectrl.session_id` is generated for each top-level agent invocation
- [ ] `TRACECTRL_SESSION_ID` env var overrides automatic generation (for tests)

---

## 8. Span Schema

This is the most critical section. Every span emitted by the SDK must carry these attributes. The Risk Engine depends on them. Do not omit fields — emit `None`/empty string if not applicable.

### 8.1 Standard OpenInference Fields (Required)

These follow the [OpenInference semantic conventions](https://github.com/Arize-ai/openinference).

| Attribute | Type | Description | Example |
|---|---|---|---|
| `openinference.span.kind` | string | Type of span | `"AGENT"`, `"LLM"`, `"TOOL"`, `"CHAIN"`, `"RETRIEVER"`, `"EMBEDDING"` |
| `input.value` | string | Full input to this component | Prompt string, tool input JSON |
| `input.mime_type` | string | MIME type of input | `"text/plain"`, `"application/json"` |
| `output.value` | string | Full output from this component | LLM response, tool output |
| `output.mime_type` | string | MIME type of output | `"text/plain"`, `"application/json"` |
| `llm.model_name` | string | Model identifier | `"gemini-2.0-flash"`, `"claude-sonnet-4-5"` |
| `llm.token_count.prompt` | int | Prompt tokens used | `512` |
| `llm.token_count.completion` | int | Completion tokens used | `256` |
| `llm.token_count.total` | int | Total tokens | `768` |
| `llm.invocation_parameters` | string (JSON) | Model call parameters | `{"temperature": 0.7, "max_tokens": 1024}` |
| `llm.system` | string | System prompt text | Full system prompt string |
| `llm.prompt_template.template` | string | Prompt template (if used) | Template string with variables |
| `llm.prompt_template.variables` | string (JSON) | Variables injected | `{"user_query": "...", "context": "..."}` |
| `tool.name` | string | Name of the tool called | `"send_email"`, `"execute_python"` |
| `tool.description` | string | Tool's declared description | Tool docstring or schema description |
| `tool.parameters` | string (JSON) | Parameters passed to the tool | Full params JSON |
| `retrieval.documents` | string (JSON) | Documents retrieved from vector store | Array of `{id, score, content, metadata}` |
| `embedding.model_name` | string | Model used for embeddings | `"text-embedding-3-small"` |

### 8.2 TraceCtrl-Specific Fields (Required — Risk Engine depends on these)

| Attribute | Type | Description | Example |
|---|---|---|---|
| `tracectrl.agent.id` | string | Stable identifier for the agent (deterministic from name+version) | `"tc-agent-a1b2c3"` |
| `tracectrl.agent.name` | string | Human-readable agent name | `"EmailResponderAgent"` |
| `tracectrl.agent.role` | string | Declared role/purpose | `"email_assistant"`, `"finance_validator"` |
| `tracectrl.agent.framework` | string | Agentic framework | `"langchain"`, `"crewai"`, `"google-adk"`, `"strands"`, `"agno"` |
| `tracectrl.agent.framework_version` | string | Framework version | `"0.3.1"` |
| `tracectrl.session_id` | string | Session UUID for this agent run | `"sess-uuid4"` |
| `tracectrl.caller.agent_id` | string | ID of the calling agent (for inter-agent calls) | `"tc-agent-d4e5f6"` — empty if top-level user call |
| `tracectrl.caller.agent_name` | string | Name of the calling agent | `"OrchestratorAgent"` |
| `tracectrl.input.source` | string | Origin classification of the input | `"user"`, `"agent"`, `"external"`, `"memory"` |
| `tracectrl.tool.category` | string | Risk category of the tool | `"code_execution"`, `"external_api"`, `"internal_api"`, `"email"`, `"memory_write"`, `"memory_read"`, `"human_interaction"`, `"file_system"` |
| `tracectrl.tool.target` | string | Target resource of the tool call | `"user@domain.com"` for email, URL for HTTP, file path for file ops |
| `tracectrl.memory.operation` | string | Memory operation type | `"read"`, `"write"`, `"delete"` — only on RETRIEVER/EMBEDDING spans |
| `tracectrl.memory.store_id` | string | Identifier of the vector store or memory backend | `"hr-docs-chroma"`, `"redis://localhost:6379/0"` |
| `tracectrl.memory.write_provenance` | string | Source classification of what is being written | `"user"`, `"agent"`, `"external"` — only on write operations |
| `tracectrl.system_prompt_hash` | string | SHA256 of the system prompt (first 8 chars) | `"a3f7b2c1"` — used to detect system prompt drift |
| `tracectrl.span_sequence` | int | Ordinal position of this span within the session | `0`, `1`, `2`... — enables ordered sequence analysis |

### 8.3 Span Kind Decision Logic

```
Event type               → openinference.span.kind
─────────────────────────────────────────────────
Agent invocation start   → AGENT
LLM API call             → LLM
Tool call                → TOOL
Chain/pipeline step      → CHAIN
Vector store read        → RETRIEVER
Embedding generation     → EMBEDDING
Agent-to-agent call      → AGENT (child span with tracectrl.caller.agent_id set)
```

### 8.4 `tracectrl.input.source` Classification Rules

The SDK must classify the input source for every span. Use this logic:

```
Input source classification:
- "user"      → span is a top-level invocation, tracectrl.caller.agent_id is empty
- "agent"     → span is invoked by another agent, tracectrl.caller.agent_id is set
- "external"  → input contains content fetched from external sources (email body, HTTP response, web scrape)
                 detected by checking if a TOOL span with category "external_api" or "email"
                 precedes this span in the same trace, AND the output of that tool appears in this span's input
- "memory"    → input contains retrieved content from a RETRIEVER span in the same trace
```

The `external` and `memory` classifications are the most security-critical — they are the primary signals for ASI01 (injection via external content) and ASI06 (memory poisoning).

---

## 9. Framework Instrumentors

### 9.1 Pattern: All Instrumentors

Every instrumentor follows this interface:

```python
class FWInstrumentor:
    """
    Base interface all TraceCtrl instrumentors must implement.
    """

    def instrument(
        self,
        *,
        tracer_provider=None,    # Optional: inject custom TracerProvider (useful for tests)
        skip_dep_check=False,    # If True, don't raise if framework not installed
    ) -> None:
        """
        Monkey-patches the target framework to emit OTLP spans.
        Idempotent — safe to call multiple times.
        """
        raise NotImplementedError

    def uninstrument(self) -> None:
        """
        Removes all patches. Used in tests and teardown.
        """
        raise NotImplementedError

    @property
    def instrumented(self) -> bool:
        """Returns True if instrument() has been called and not yet uninstrumented."""
        raise NotImplementedError
```

**Acceptance criteria for ALL instrumentors:**
- [ ] `instrument()` is idempotent — calling it twice does not double-emit spans
- [ ] `uninstrument()` fully removes all patches and no spans are emitted after it
- [ ] `instrument()` raises `ImportError` with a clear message if the target framework is not installed (unless `skip_dep_check=True`)
- [ ] All emitted spans include every field in the TraceCtrl span schema (Section 7)
- [ ] Spans are emitted within 100ms of the event they represent
- [ ] Failed span export (OTel Collector unreachable) does not raise an exception in the agent process when `TRACECTRL_FAIL_SILENTLY=true`

---

### 9.2 LangChain / LangGraph

**Package:** `tracectrl-instrumentation-langchain`

```python
pip install tracectrl tracectrl-instrumentation-langchain
```

```python
from tracectrl.instrumentation.langchain import LangChainInstrumentor

LangChainInstrumentor().instrument()

# Your existing LangChain/LangGraph code — unchanged
from langchain_core.runnables import RunnableLambda
chain = RunnableLambda(my_fn)
chain.invoke({"input": "hello"})
```

**What it instruments:**

| LangChain Event | Span Kind | Notes |
|---|---|---|
| `Chain.invoke` / `Chain.ainvoke` | `CHAIN` | Top-level chain invocations |
| `ChatModel.invoke` / `ainvoke` | `LLM` | Every LLM call; captures system prompt hash |
| `Tool.run` / `arun` | `TOOL` | Every tool invocation; infers `tracectrl.tool.category` from tool name/type |
| `VectorStoreRetriever.get_relevant_documents` | `RETRIEVER` | Sets `tracectrl.memory.operation = "read"` |
| `VectorStore.add_documents` | `RETRIEVER` | Sets `tracectrl.memory.operation = "write"`, classifies `tracectrl.memory.write_provenance` |
| `BaseAgent.plan` | `AGENT` | Agent planning steps |
| LangGraph `StateGraph` node execution | `AGENT` | Each node = one AGENT span; state transitions captured in `output.value` |
| LangGraph `StateGraph` edge traversal | `CHAIN` | Edge conditions and routing captured |

**LangGraph-specific requirements:**
- Each `StateGraph` node must emit a span with `tracectrl.agent.name` set to the node name
- State diffs (what changed in the graph state between nodes) must be captured in a `tracectrl.langgraph.state_diff` attribute (JSON string of added/changed keys)
- Multi-agent LangGraph architectures (graphs that call other graphs) must propagate `trace_id` across the sub-graph boundary

**Acceptance criteria:**
- [ ] Single-agent LangChain chain produces one CHAIN parent span with LLM and TOOL child spans
- [ ] LangGraph state machine produces one AGENT span per node with `tracectrl.agent.name` = node name
- [ ] LangGraph state transitions are captured including which edge was taken
- [ ] Vector store reads produce RETRIEVER spans with `tracectrl.memory.operation = "read"`
- [ ] Vector store writes produce RETRIEVER spans with `tracectrl.memory.operation = "write"` and correct `tracectrl.memory.write_provenance`
- [ ] Multi-graph architectures share `trace_id` across graph boundaries

---

### 9.3 Google ADK

**Package:** `tracectrl-instrumentation-google-adk`

```python
pip install tracectrl tracectrl-instrumentation-google-adk
```

```python
from tracectrl.instrumentation.google_adk import ADKInstrumentor

ADKInstrumentor().instrument()

# Your existing ADK code — unchanged
from google.adk import Agent
agent = Agent(name="my-agent", model="gemini-2.0-flash", tools=[...])
agent.run("Do a task")
```

**What it instruments:**

| ADK Event | Span Kind | Notes |
|---|---|---|
| `Agent.run` / `Agent.run_async` | `AGENT` | Top-level run; `tracectrl.agent.name` = `agent.name` |
| LLM invocations within ADK | `LLM` | Model calls; captures `llm.system` from agent instruction |
| Function tool calls | `TOOL` | Every `FunctionTool` call; infers tool category |
| `AgentTool` calls (agent calling another agent) | `AGENT` | Sub-agent call; sets `tracectrl.caller.agent_id` on child spans |
| Multi-agent runner orchestration | `CHAIN` | Parent span for the full orchestration run |

**ADK-specific requirements:**
- `tracectrl.agent.role` is populated from `agent.description` if available
- When an `AgentTool` is called (ADK agent calling another ADK agent), the child agent's spans must have `tracectrl.caller.agent_id` set to the parent agent's ID
- The ADK `session_id` (ADK's own concept) must be captured as `tracectrl.adk.session_id` (separate from TraceCtrl's `tracectrl.session_id`)

**Acceptance criteria:**
- [ ] Single ADK agent produces AGENT → LLM + TOOL span tree
- [ ] Multi-agent ADK pipeline (AgentTool) produces correct parent-child span hierarchy with `tracectrl.caller.agent_id` set
- [ ] `tracectrl.agent.name` matches `agent.name` from ADK config
- [ ] `llm.system` captures the agent's instruction string

---

### 9.4 CrewAI

**Package:** `tracectrl-instrumentation-crewai`

```python
pip install tracectrl tracectrl-instrumentation-crewai
```

```python
from tracectrl.instrumentation.crewai import CrewAIInstrumentor

CrewAIInstrumentor().instrument()

# Your existing CrewAI code — unchanged
from crewai import Crew, Agent, Task
crew = Crew(agents=[...], tasks=[...])
crew.kickoff()
```

**What it instruments (OpenInference pattern — recommended):**

| CrewAI Event | Span Kind | Notes |
|---|---|---|
| `Crew.kickoff` | `CHAIN` | Top-level crew run; captures crew config metadata |
| Per-agent task assignment | `AGENT` | One AGENT span per agent-task pairing; `tracectrl.agent.name` = agent role |
| LLM calls within agent | `LLM` | Per-LLM-invocation spans |
| Tool calls within agent | `TOOL` | Per-tool-call spans with category inference |
| Agent collaboration messages | `CHAIN` | When agents pass results to each other |

**Alternative: `crewai_event_bus.on()` pattern**
CrewAI exposes a native event bus. If OpenInference hooks are insufficient, subscribe to:
- `CrewKickoffStartedEvent`
- `CrewKickoffCompletedEvent`
- `AgentExecutionStartedEvent`
- `AgentExecutionCompletedEvent`
- `ToolUsageStartedEvent`
- `ToolUsageFinishedEvent`

The OpenInference pattern is preferred as it gives richer LLM-level data. Use the event bus for events not covered by OpenInference.

**Acceptance criteria:**
- [ ] `Crew.kickoff()` produces one CHAIN span as root
- [ ] Each agent in the crew produces at least one AGENT span
- [ ] Each task assignment is captured with `tracectrl.agent.role` = agent's role name
- [ ] Tool calls produce TOOL spans with `tracectrl.tool.name` and `tracectrl.tool.category`
- [ ] LLM calls per agent are captured with `llm.model_name`
- [ ] Errors (agent execution failures) are captured as span errors with full traceback in `exception.stacktrace`

---

### 9.5 AWS Strands

**Package:** `tracectrl-instrumentation-strands`

```python
pip install tracectrl tracectrl-instrumentation-strands
```

```python
from tracectrl.instrumentation.strands import StrandsInstrumentor

StrandsInstrumentor().instrument()

# Your existing Strands code — unchanged
from strands import Agent
agent = Agent(tools=[...])
agent("Do a task")
```

**Package:** `openinference-instrumentation-strands`

`StrandsInstrumentor` follows the identical OI wrap pattern as all other frameworks — call the OI instrumentor, register the TraceCtrlSpanProcessor. No special env var handling needed.

**What it instruments:**

| Strands Event | Span Kind | Notes |
|---|---|---|
| Agent invocation | `AGENT` | Captured by OI instrumentor; enriched with `tracectrl.*` by SpanProcessor |
| Tool calls | `TOOL` | Captured by OI instrumentor; enriched with `tracectrl.tool.category` by SpanProcessor |
| Bedrock API calls | `LLM` | Captures model ID, token counts |
| Session metadata | Attributes on AGENT span | `tracectrl.session_id` set |

**Acceptance criteria:**
- [ ] `StrandsInstrumentor().instrument()` does not break existing Strands OTel configuration if already set
- [ ] All spans emitted by Strands are enriched with `tracectrl.*` attribute set
- [ ] `tracectrl.agent.framework = "strands"` is set on all agent spans
- [ ] Bedrock model ID is captured in `llm.model_name`

---

### 9.6 Agno

**Package:** `tracectrl-instrumentation-agno`

```python
pip install tracectrl tracectrl-instrumentation-agno
```

```python
from tracectrl.instrumentation.agno import AgnoInstrumentor

AgnoInstrumentor().instrument()

# Your existing Agno code — unchanged
from agno.agent import Agent
agent = Agent(name="my-agent", tools=[...], knowledge=[...])
agent.run("Do a task")
```

**What it instruments:**

| Agno Event | Span Kind | Notes |
|---|---|---|
| `Agent.run` / `Agent.arun` | `AGENT` | Top-level run |
| LLM calls | `LLM` | Per-invocation |
| Tool calls | `TOOL` | Per-tool; `tracectrl.tool.category` inferred |
| Memory reads (knowledge base queries) | `RETRIEVER` | `tracectrl.memory.operation = "read"` |
| Memory writes | `RETRIEVER` | `tracectrl.memory.operation = "write"` with provenance |
| Multi-agent team coordination | `CHAIN` + `AGENT` | Team run = CHAIN; each agent in team = AGENT child |
| Step-level traces | `CHAIN` | Each agent reasoning step |

**Agno-specific requirements:**
- Agno's knowledge base queries must emit RETRIEVER spans with `retrieval.documents` populated
- When Agno's multi-agent Team is used, each member agent produces its own AGENT span hierarchy, all under one CHAIN root span for the Team.run()

**Acceptance criteria:**
- [ ] Single Agno agent produces AGENT → LLM + TOOL spans
- [ ] Knowledge base queries produce RETRIEVER spans with document metadata
- [ ] Memory writes capture `tracectrl.memory.write_provenance` based on input source chain
- [ ] Multi-agent Team runs produce correct hierarchy: CHAIN (Team) → AGENT (per member) → LLM/TOOL

---

## 10. MCP Server — Cursor + Claude Code Integration

**Package:** `tracectrl-mcp`

```python
pip install tracectrl-mcp
```

**Cursor configuration** (`.cursorrules` or MCP server config):
```json
{
  "mcpServers": {
    "tracectrl": {
      "command": "tracectrl-mcp",
      "env": {
        "TRACECTRL_ENDPOINT": "http://localhost:4317"
      }
    }
  }
}
```

**Claude Code configuration** (`~/.claude.json` or project `.mcp.json`):
```json
{
  "mcpServers": {
    "tracectrl": {
      "command": "tracectrl-mcp",
      "env": {
        "TRACECTRL_ENDPOINT": "http://localhost:4317"
      }
    }
  }
}
```

### 10.1 How the MCP Server Works

The TraceCtrl MCP server is a **transparent proxy**. It:
1. Starts as an MCP server process
2. Registers the same tools as the downstream MCP server(s) the agent is using
3. Intercepts every tool call, emits a TOOL span, then forwards the call to the actual MCP server
4. Intercepts the response, emits the response as the span output, then returns it to the agent

The agent is unaware of the proxy. From its perspective, it is calling tools normally.

```
Agent (Cursor/Claude Code)
    │
    ▼
TraceCtrl MCP Proxy ──── emits TOOL span ──→ OTel Collector
    │
    ▼
Actual MCP Server (GitHub, filesystem, browser-tools, etc.)
```

### 10.2 Tool Schema Scanner

At startup, the MCP server scans all registered tool schemas (name, description, inputSchema) for instruction-like patterns using a lightweight classifier. This is **Tier 1 detection for ASI04 (Supply Chain)**.

```python
# schema_scanner.py — run at MCP server startup
def scan_tool_schema(tool: MCPTool) -> Optional[RiskSignal]:
    """
    Scans a tool's schema for instruction-like content.
    Returns a RiskSignal if suspicious content is found, else None.
    Emits the signal as a span attribute: tracectrl.schema_scan_result
    """
```

The scanner checks:
- Tool `description` field for phrases that override agent behaviour (e.g. "ignore previous instructions", "you are now", "your new role is")
- Tool `inputSchema` property descriptions for injection patterns
- Tool name for impersonation patterns (e.g. a tool named `send_to_admin` that the schema says sends to an attacker)

If a suspicious pattern is found, the TOOL span emitted for that tool includes:
- `tracectrl.schema_scan_result = "suspicious"`
- `tracectrl.schema_scan_pattern = "<matched_pattern>"`

### 10.3 MCP Server Acceptance Criteria

- [ ] `tracectrl-mcp` starts and registers as a valid MCP server consumable by Cursor and Claude Code
- [ ] Every tool call through the proxy produces a TOOL span with full `tracectrl.*` schema
- [ ] Schema scanner runs at startup and flags known injection patterns in tool descriptors
- [ ] The proxy adds less than 2ms latency per tool call
- [ ] Proxy is transparent — agent output is identical to calling the underlying MCP server directly
- [ ] If the underlying MCP server is unreachable, the proxy returns the same error the agent would have received without the proxy

---

## 11. Tool Category Inference

The `tracectrl.tool.category` field is critical for the Risk Engine's Tier 2 anomaly detector. The SDK must infer it automatically without requiring developers to declare it. Use this logic:

```python
TOOL_CATEGORY_RULES = [
    # (match_fn, category)
    # Match by tool name keywords
    (lambda name, desc: any(k in name.lower() for k in ["exec", "run_code", "python", "bash", "shell", "eval", "compile"]),
     "code_execution"),

    (lambda name, desc: any(k in name.lower() for k in ["send_email", "send_mail", "email", "smtp"]),
     "email"),

    (lambda name, desc: any(k in name.lower() for k in ["http", "fetch", "request", "curl", "scrape", "browse", "web"]),
     "external_api"),

    (lambda name, desc: any(k in name.lower() for k in ["write_file", "save_file", "create_file", "delete_file", "rm", "mv"]),
     "file_system"),

    (lambda name, desc: any(k in name.lower() for k in ["vector", "embed", "upsert", "add_document", "index"]),
     "memory_write"),

    (lambda name, desc: any(k in name.lower() for k in ["search", "query", "retrieve", "recall", "lookup"]),
     "memory_read"),

    (lambda name, desc: any(k in name.lower() for k in ["human", "approval", "confirm", "ask_user", "hitl"]),
     "human_interaction"),

    # Default for anything else
    (lambda name, desc: True, "internal_api"),
]

def infer_tool_category(tool_name: str, tool_description: str = "") -> str:
    for match_fn, category in TOOL_CATEGORY_RULES:
        if match_fn(tool_name, tool_description):
            return category
    return "internal_api"
```

This list is a starting point. Add rules as new tools are encountered in customer deployments.

---

## 12. Trace Context Propagation for Multi-Agent Systems

This is the most technically complex part of the SDK. When Agent A calls Agent B, Agent B's spans must be children of Agent A's span in the same trace.

### 12.1 Same-Process Multi-Agent

When agents call each other within the same Python process (e.g. LangGraph calling a sub-agent, CrewAI team):

```python
# The calling agent's span context is automatically propagated
# via Python's contextvars — no manual work needed
# The child agent's instrumentor picks up the active span from the context
```

### 12.2 Cross-Process Multi-Agent (HTTP/gRPC)

When agents communicate across process boundaries:

```python
# SDK provides helpers to inject and extract trace context
from tracectrl.context import inject_trace_headers, extract_trace_headers

# Calling agent — inject before making the HTTP call
headers = {}
inject_trace_headers(headers)
response = requests.post("http://agent-b/run", headers=headers, json=payload)

# Receiving agent (Agent B) — extract at the start of its handler
from tracectrl.context import extract_trace_headers
extract_trace_headers(request.headers)
# Now the active span context is linked to Agent A's trace
```

### 12.3 MCP Cross-Agent Context

For MCP-based agent calls, the trace context is injected into the MCP tool call metadata:

```json
{
  "_tracectrl": {
    "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
    "tracectrl_session_id": "sess-abc123"
  }
}
```

The receiving MCP server (proxied by TraceCtrl MCP) extracts this and links the spans.

**Acceptance criteria:**
- [ ] Same-process multi-agent: all agents in the run share `trace_id`; parent-child span hierarchy is correct
- [ ] Cross-process multi-agent with HTTP: `inject_trace_headers` / `extract_trace_headers` correctly propagate W3C `traceparent` header
- [ ] When `tracectrl.caller.agent_id` is populated, `parent_span_id` points to the caller agent's span
- [ ] Traces without explicit context propagation still work (produce a new root span, not an error)

---

## 13. Implementation Plan

### Phase 1 — Sprint 3 (Priority: must ship)

**Goal:** Core SDK + LangChain/LangGraph + Google ADK + MCP server working end-to-end.

| Task | Owner signal | Estimate | Dependency |
|---|---|---|---|
| `tracectrl` core package: config, exporter, session, schema constants | Backend | 2 days | None |
| Span schema definition: all attributes in Section 7 defined as typed constants | Backend | 0.5 days | None |
| Tool category inference (`infer_tool_category`) | Backend | 0.5 days | Core package |
| `tracectrl-instrumentation-langchain`: Chain, LLM, Tool hooks | Backend | 3 days | Core package |
| LangGraph state machine hooks (node + edge spans) | Backend | 2 days | LangChain instrumentor |
| `tracectrl-instrumentation-google-adk`: Agent, LLM, Tool, AgentTool hooks | Backend | 3 days | Core package |
| Multi-agent context propagation (same-process) | Backend | 1 day | Core package |
| `tracectrl-mcp`: proxy server + schema scanner | Backend | 3 days | Core package |
| End-to-end integration test: Email Assistant scenario (ASI01) | QA/Backend | 1 day | LangChain + MCP |
| End-to-end integration test: IDE Coding Agent scenario (ASI05) | QA/Backend | 1 day | MCP |
| OTel Collector config to receive from SDK (Component 2 interface) | Infra | 1 day | Core package |

**Phase 1 done criteria:** The Email Assistant scenario produces a trace visible in the OTel Collector with all required span fields populated.

---

### Phase 2 — Sprint 4 (Priority: complete framework coverage)

**Goal:** CrewAI + Strands + Agno instrumented. Cross-process context propagation. Full OWASP scenario test coverage.

| Task | Owner signal | Estimate | Dependency |
|---|---|---|---|
| `tracectrl-instrumentation-crewai` | Backend | 2.5 days | Core package |
| `tracectrl-instrumentation-strands` (OI wrap pattern) | Backend | 1 day | Core package |
| `tracectrl-instrumentation-agno` | Backend | 2.5 days | Core package |
| Cross-process context propagation (`inject_trace_headers`, `extract_trace_headers`) | Backend | 1.5 days | Core package |
| MCP cross-agent context via `_tracectrl` metadata injection | Backend | 1 day | MCP server |
| `tracectrl.memory.write_provenance` classification logic | Backend | 1.5 days | All instrumentors |
| `tracectrl.input.source` classification logic | Backend | 1 day | All instrumentors |
| Integration test: Expense Approval scenario (ASI03) | QA | 1 day | Cross-process context |
| Integration test: HR RAG Chatbot scenario (ASI06) | QA | 1 day | Memory provenance |
| Integration test: MCP Supply Chain scenario (ASI04) | QA | 0.5 days | Schema scanner |
| PyPI packaging + README for all 6 packages | Backend | 1 day | All packages |

**Phase 2 done criteria:** All 5 TAGAAI attack scenarios produce correct traces with all expected span fields. All 6 packages published to PyPI.

---

### Phase 3 — Sprint 5+ (Future scope)

| Task | Notes |
|---|---|
| TypeScript/JS SDK (`tracectrl-js`) | For Vercel AI SDK, LangChain.js |
| Policy declaration API in SDK config | Input to Component 3 Policy Console |
| OTel Sampling support | For high-volume deployments |
| `tracectrl guard` — blocking mode | Component 4: intercept + block, not just observe |
| SDK for AutoGen | If customer demand confirms |

---

## 14. Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| Time to first trace (developer installs, instruments, sees span) | < 5 minutes | User test with 3 external engineers |
| Span field completeness | 100% of required fields populated on every span | Automated schema validation in test suite |
| Latency overhead per LLM call | < 5ms p99 | Benchmark: 1000 LLM calls with/without SDK |
| Latency overhead per tool call | < 1ms p99 | Benchmark: 1000 tool calls with/without SDK |
| SDK adoption (instrumented agent runs in first 30 days post-launch) | 50+ unique deployments | OTel Collector span count by `service.name` |
| Framework coverage | All 5 frameworks + MCP by Sprint 4 | Instrumentation test pass rate |
| Integration test pass rate (5 TAGAAI scenarios) | 100% | CI pipeline |

---

## 15. Open Questions

| # | Question | Owner | Blocking? |
|---|---|---|---|
| 1 | Should `input.value` and `output.value` be truncated at a max length for high-token LLM calls? Sending full multi-thousand-token prompts as span attributes may create large payloads. | Eng + Product | No — default to no truncation for MVP; add configurable truncation in Phase 2 |
| 2 | How do we handle frameworks that call the LLM API directly (not via LangChain abstraction)? Should we instrument `openai.ChatCompletion`, `anthropic.messages.create` directly? | Eng | Yes — needed for ADK and Agno which use model clients directly |
| 3 | What is the OTel Collector's ClickHouse schema? The `tracectrl.*` attributes need to map to ClickHouse columns. This must be agreed with the Component 2 team before Sprint 3 starts. | Infra + Backend | **Yes — blocking for Sprint 3 start** |
| 4 | Does the MCP proxy approach work with all MCP client implementations (Cursor, Claude Code, custom)? Need to test with both before Sprint 3 ships. | Eng | Yes — needs validation |
| 5 | Should `tracectrl.system_prompt_hash` use the full system prompt or just the first N tokens? Long system prompts may not be stable enough for hash comparison. | Eng | No — use full prompt for now; revisit if false positives appear |

---

## 16. Acceptance Criteria — End-to-End

These are the integration tests that define "SDK is done". Each maps to one of the five TAGAAI attack scenarios.

### Scenario 1 — Email Assistant (ASI01: Goal Hijack)
```
Given a LangChain agent instrumented with LangChainInstrumentor
  And the agent has a send_email tool
  And the agent's input is an email body containing injection text
When the agent runs
Then the trace contains:
  - An AGENT root span with tracectrl.agent.name set
  - An LLM span with input.value containing the email body
  - A TOOL span with tool.name = "send_email" and tracectrl.tool.category = "email"
  - tracectrl.input.source = "external" on the LLM span that processes the email body
  - All spans sharing the same trace_id
```

### Scenario 2 — Expense Approval (ASI03: Identity Abuse)
```
Given a multi-agent ADK pipeline (OrchestratorAgent → FinanceAgent → PaymentAgent)
  And each agent is instrumented with ADKInstrumentor
  And agents communicate over HTTP with inject/extract context helpers
When the full pipeline runs
Then the trace contains:
  - Three AGENT spans sharing the same trace_id
  - tracectrl.caller.agent_id on FinanceAgent's span = OrchestratorAgent's tracectrl.agent.id
  - tracectrl.caller.agent_id on PaymentAgent's span = FinanceAgent's tracectrl.agent.id
  - Parent-child span hierarchy matches the agent call order
```

### Scenario 3 — IDE Coding Agent (ASI05: RCE Chain)
```
Given a Claude Code session with the TraceCtrl MCP server installed
  And the agent reads a repository file, generates code, and executes it
When the session runs
Then the trace contains:
  - A TOOL span for the file read with tracectrl.tool.category = "file_system"
  - An LLM span for code generation
  - A TOOL span for code execution with tracectrl.tool.category = "code_execution"
  - All three spans in causal order (file read → LLM → exec) within the same trace
  - tracectrl.input.source = "external" on the code generation LLM span (input came from file)
```

### Scenario 4 — HR RAG Chatbot (ASI06: Memory Poisoning)
```
Given a LangChain RAG agent instrumented with LangChainInstrumentor
  And an employee submits feedback that is indexed into the vector store
When the feedback is indexed
Then the trace contains:
  - A RETRIEVER span with tracectrl.memory.operation = "write"
  - tracectrl.memory.write_provenance = "external" (the feedback came from user input, not internal agent)
  - The write span's input.value contains the feedback content
```

### Scenario 5 — MCP Supply Chain (ASI04: Tool Descriptor Override)
```
Given the TraceCtrl MCP server is running
  And a tool with an injection pattern in its description is registered
When the MCP server starts and scans tool schemas
Then:
  - The first TOOL span emitted for that tool contains tracectrl.schema_scan_result = "suspicious"
  - tracectrl.schema_scan_pattern = <the matched pattern>
  - The scan result is also emitted as a startup warning log
```

---

*This spec is authoritative for Component 1 of the TraceCtrl MVP 2.0. Questions → TraceCtrl product team. Implementation questions → open an issue in the tracectrl/tracectrl-sdk repo.*
