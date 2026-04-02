# OpenClaw OTEL Integration Plan

## Context

OpenClaw is a self-hosted AI messaging gateway that bridges chat platforms (WhatsApp, Telegram, Discord, Slack, iMessage, etc.) to AI agents. It natively exports OpenTelemetry traces, metrics, and logs via OTLP/HTTP.

This plan details how to integrate OpenClaw's trace telemetry into the TraceCtrl observability pipeline.

---

## What OpenClaw Exports

### Spans (5 types) — What We Ingest

| Span Name | Maps To | Key Attributes |
|-----------|---------|----------------|
| `openclaw.model.usage` | LLM call | `channel`, `provider`, `model`, `sessionKey`, `sessionId`, tokens (input/output/cache_read/cache_write/total) |
| `openclaw.webhook.processed` | Inbound message handling | `channel`, `webhook`, `chatId` |
| `openclaw.webhook.error` | Failed webhook | `channel`, `webhook`, `chatId`, `error` |
| `openclaw.message.processed` | Full message lifecycle | `channel`, `outcome`, `chatId`, `messageId`, `sessionKey`, `sessionId`, `reason` |
| `openclaw.session.stuck` | Stuck session alert | `state`, `ageMs`, `queueDepth`, `sessionKey`, `sessionId` |

### Metrics & Logs — Intentionally Deferred

OpenClaw also exports 20+ metrics (token counters, cost, latency histograms) and structured logs. We **do not process these in this sprint**. The OTel collector silently drops signals with no configured pipeline — no errors, no backpressure to OpenClaw. Traces alone provide everything needed for topology, sessions, and risk views.

**When to add metrics:** Sprint 3+ when cost tracking and operational dashboards are needed. It's a 5-minute collector config change — no code.

---

## Integration Architecture

```
Chat Platforms (WhatsApp, Telegram, Discord, ...)
         ↓
┌─────────────────────────────────────────────┐
│  OpenClaw Gateway                           │
│                                             │
│  diagnostics-otel plugin                    │
│  └── Traces → OTLP/HTTP :4318              │
└──────────────┬──────────────────────────────┘
               ↓
┌─────────────────────────────────────────────┐
│  TraceCtrl OTel Collector :4318             │
│  (existing — no config changes needed)      │
│                                             │
│  traces pipeline → ClickHouse otel_traces   │
└──────────────┬──────────────────────────────┘
               ↓
┌─────────────────────────────────────────────┐
│  TraceCtrl Engine Pipeline                  │
│                                             │
│  Span extraction (NEW):                     │
│  openclaw.model.usage    → LLM inventory    │
│  openclaw.message.*      → Session tracking │
│  openclaw.webhook.*      → Channel topology │
│  openclaw.session.stuck  → Alert/risk       │
└──────────────┬──────────────────────────────┘
               ↓
┌─────────────────────────────────────────────┐
│  Dashboard :3000                            │
│  Project: openclaw-gateway                  │
│                                             │
│  Topology: channels → gateway → models      │
│  Sessions: message lifecycle with LLM calls │
│  Risk: stuck sessions, webhook errors       │
└─────────────────────────────────────────────┘
```

**Key:** No infrastructure changes. The collector already accepts OTLP/HTTP on :4318 and writes traces to ClickHouse. OpenClaw spans land in `otel_traces` automatically. We only need pipeline logic to interpret them.

---

## Implementation Plan

### Phase 1: Span Attribute Extraction (2 hours)

**File:** `engine/db/spans.py`

OpenClaw uses custom attributes (`channel`, `provider`, `model`, `sessionId`, `chatId`, `outcome`) not present in our current extraction map. Add OpenClaw-specific attribute extraction to `fetch_new_spans`:

```python
# Inside the span dict construction, add:
"_oc_channel": attrs.get("channel", "") or attrs.get("openclaw.channel", ""),
"_oc_provider": attrs.get("provider", "") or attrs.get("openclaw.provider", ""),
"_oc_model": attrs.get("model", "") or attrs.get("openclaw.model", ""),
"_oc_session_id": attrs.get("sessionId", "") or attrs.get("openclaw.sessionId", ""),
"_oc_outcome": attrs.get("outcome", "") or attrs.get("openclaw.outcome", ""),
"_oc_chat_id": attrs.get("chatId", "") or attrs.get("openclaw.chatId", ""),
```

Then add post-processing block after the existing Strands/Agno blocks:

```python
# Post-process: derive identity from OpenClaw spans
for span in spans:
    name = span["span_name"]
    if not name.startswith("openclaw."):
        continue

    if name == "openclaw.model.usage":
        span["oi_span_kind"] = "LLM"
        span["llm_model_name"] = span["_oc_model"] or span["llm_model_name"]
        span["tc_agent_framework"] = "openclaw"

    elif name == "openclaw.message.processed":
        span["oi_span_kind"] = "AGENT"
        channel = span["_oc_channel"]
        span["tc_agent_name"] = f"openclaw-{channel}" if channel else "openclaw-gateway"
        span["tc_agent_id"] = span["tc_agent_name"]
        span["tc_agent_framework"] = "openclaw"

    elif name == "openclaw.webhook.processed":
        span["oi_span_kind"] = "TOOL"
        span["tool_name"] = f"webhook:{span['_oc_channel']}" if span["_oc_channel"] else "webhook_handler"
        span["tc_tool_category"] = "external_api"
        span["tc_agent_framework"] = "openclaw"

    elif name == "openclaw.webhook.error":
        span["oi_span_kind"] = "TOOL"
        span["tool_name"] = f"webhook:{span['_oc_channel']}" if span["_oc_channel"] else "webhook_handler"
        span["status_code"] = "ERROR"
        span["tc_tool_category"] = "external_api"
        span["tc_agent_framework"] = "openclaw"

    elif name == "openclaw.session.stuck":
        span["oi_span_kind"] = "AGENT"
        span["tc_agent_name"] = "openclaw-session-monitor"
        span["tc_agent_id"] = "openclaw-session-monitor"
        span["tc_agent_framework"] = "openclaw"
        span["status_code"] = "ERROR"

    # Session ID from OpenClaw
    if not span["tc_session_id"]:
        span["tc_session_id"] = span["_oc_session_id"]
```

### Phase 2: Framework Detection in Service Filter (30 min)

**File:** `engine/db/topology.py`

Update `_get_agent_ids_for_service` to handle OpenClaw span names:

```python
# Add alongside the existing invoke_agent / .run patterns:
elif span_name.startswith("openclaw.message"):
    name = "openclaw-" + (attrs.get("channel", "") or "gateway")
```

### Phase 3: UI Framework Support (1 hour)

**File:** `ui/src/lib/spanUtils.ts`

Add OpenClaw to color and emoji maps:

```typescript
// SPAN_KIND_COLORS:
OPENCLAW: '#FF6B9D',  // Pink — visually distinct from other frameworks

// TraceTreeView.tsx SPAN_TYPE_EMOJI:
OPENCLAW: '🦞',
```

**File:** `ui/src/styles/globals.css`

Add badge style:
```css
.badge-openclaw { color: #FF6B9D; background: rgba(255, 107, 157, 0.12); }
```

### Phase 4: Topology Model (1 hour)

**File:** `engine/db/topology.py`

When OpenClaw spans are processed, the topology renders as:

```
[openclaw-whatsapp]  ──webhook──→  [model: claude-sonnet-4-6]
[openclaw-telegram]  ──webhook──→  [model: gpt-4o]
[openclaw-discord]   ──webhook──→  [model: gemini-2.5-pro]
```

Each channel becomes an agent node. Each model becomes an LLM-type tool node via the existing agent→tool edge building (the `openclaw.model.usage` span's `_oc_model` value flows through the parent-child resolution).

No special topology code needed — the span extraction in Phase 1 maps OpenClaw data into the same `tc_agent_id` + `tool_name` + `oi_span_kind` fields that the existing topology builder already processes.

---

## Implementation Effort

| Phase | Effort | Files |
|-------|--------|-------|
| 1. Span extraction | 2h | `engine/db/spans.py` |
| 2. Service filter | 30min | `engine/db/topology.py` |
| 3. UI framework support | 1h | `ui/src/lib/spanUtils.ts`, `ui/src/components/TraceTreeView.tsx`, `ui/src/styles/globals.css` |
| 4. Topology model | 1h | Validation only — Phase 1 mapping handles it |
| **Total** | **~4.5 hours** | **4-5 files, zero infra changes** |

---

## OpenClaw User Setup

### Step 1: Enable the plugin

```bash
openclaw plugins enable diagnostics-otel
```

### Step 2: Configure OTEL export

Add to `~/.openclaw/openclaw.json`:

```json
{
  "plugins": {
    "allow": ["diagnostics-otel"],
    "entries": {
      "diagnostics-otel": { "enabled": true }
    }
  },
  "diagnostics": {
    "enabled": true,
    "otel": {
      "enabled": true,
      "endpoint": "http://<tracectrl-host>:4318",
      "protocol": "http/protobuf",
      "serviceName": "openclaw-gateway",
      "traces": true,
      "metrics": false,
      "logs": false,
      "sampleRate": 1.0,
      "flushIntervalMs": 5000
    }
  }
}
```

### Step 3: Restart gateway

```bash
openclaw gateway restart
```

Spans appear in TraceCtrl within 5 seconds. Select `openclaw-gateway` from the project dropdown.

### Recommended Settings

| Setting | Value | Why |
|---------|-------|-----|
| `sampleRate` | `1.0` for dev, `0.2` for prod | Full tracing during setup, sample at scale |
| `flushIntervalMs` | `5000` | 5s for near-real-time. Default 60s is too slow. |
| `traces` | `true` | Required for all TraceCtrl views |
| `metrics` | `false` | Not processed yet — silently dropped, no harm |
| `logs` | `false` | High volume, not processed yet |

---

## Span-to-TraceCtrl Mapping Reference

| OpenClaw Span | TraceCtrl `oi_span_kind` | `tc_agent_id` | `tc_agent_framework` | `tool_name` | Notes |
|---------------|-------------------------|---------------|---------------------|-------------|-------|
| `openclaw.model.usage` | LLM | — | openclaw | — | `llm_model_name` from `model` attr |
| `openclaw.message.processed` | AGENT | `openclaw-{channel}` | openclaw | — | Root span per message |
| `openclaw.webhook.processed` | TOOL | — | openclaw | `webhook:{channel}` | `tc_tool_category = external_api` |
| `openclaw.webhook.error` | TOOL | — | openclaw | `webhook:{channel}` | `status_code = ERROR` |
| `openclaw.session.stuck` | AGENT | `openclaw-session-monitor` | openclaw | — | Triggers risk alert |

---

## What You'll See in TraceCtrl

### Sessions Page
- Each `openclaw.message.processed` span = one session row
- Shows: channel, outcome, duration, nested LLM calls

### Topology Page
- Channel agents (openclaw-whatsapp, openclaw-telegram) as blue nodes
- Model tools (webhook:whatsapp, webhook:telegram) as green nodes
- LLM usage edges showing which channels use which models

### Risk Dashboard
- `openclaw.session.stuck` triggers risk alerts
- `openclaw.webhook.error` tracked as error rate
- Webhook error patterns surface in attack path analysis

---

## Deferred to Sprint 3

| Feature | Effort | Description |
|---------|--------|-------------|
| Metrics pipeline | 5 min config | Add metrics exporter to `otel-collector.yaml` |
| Cost tracking | 2h | Dashboard card for `openclaw.cost.usd` aggregate |
| Latency percentiles | 2h | P50/P95/P99 from `openclaw.run.duration_ms` histogram |
| Log correlation | 3h | Link OTLP logs to spans by traceId |
| Session correlation | 3h | Link OpenClaw `sessionId` to inner agent SDK traces |
| Channel-specific views | 2h | Per-channel topology and session filtering |
