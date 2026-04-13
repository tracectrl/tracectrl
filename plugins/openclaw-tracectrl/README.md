# @tracectrl/openclaw-plugin

Security observability plugin for OpenClaw that exports rich telemetry via OpenTelemetry. Captures message content, tool calls with arguments and results, model usage, session lifecycle, and security-relevant events.

Unlike OpenClaw's built-in `diagnostics-otel` (which exports shallow operational metrics), this plugin provides the depth needed for topology views, trace exploration, and risk scoring in TraceCtrl.

## What it captures

| Hook | Span | Key attributes |
|------|------|----------------|
| `message_received` | `tracectrl.request` (root) | channel, session key, direction, message text |
| `before_agent_start` | `tracectrl.agent.turn` | agent ID, model |
| `tool_result_persist` | `tracectrl.tool.{name}` | tool name, call ID, input preview, result size, errors |
| `agent_end` | (closes agent + root) | token usage (input/output/cache), duration, model |
| `command:new/reset/stop` | `tracectrl.session.{action}` | action, session key |
| `gateway:startup` | `tracectrl.gateway.startup` | version, PID |

### Security detection

The plugin automatically flags:

- **Dangerous tools** — bash, shell, exec, subprocess
- **Dangerous commands** — rm -rf, sudo, reverse shells, piped curl/wget
- **Sensitive file access** — .env, private keys, /etc/passwd, credentials
- **Prompt injection** — "ignore previous instructions", jailbreak patterns

Findings are recorded as span attributes (`tracectrl.security.*`) and counted via the `tracectrl.security.events` metric.

### Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `tracectrl.messages.received` | Counter | Inbound messages |
| `tracectrl.messages.sent` | Counter | Outbound messages |
| `tracectrl.tool.calls` | Counter | Tool invocations |
| `tracectrl.tool.errors` | Counter | Tool errors |
| `tracectrl.tokens.total` | Counter | Total tokens |
| `tracectrl.tokens.prompt` | Counter | Input tokens |
| `tracectrl.tokens.completion` | Counter | Output tokens |
| `tracectrl.security.events` | Counter | Security events |
| `tracectrl.agent.turn.duration_ms` | Histogram | Agent turn duration |
| `tracectrl.tool.duration_ms` | Histogram | Tool call duration |

## Installation

```bash
cp -r plugins/openclaw-tracectrl ~/.openclaw/extensions/tracectrl
cd ~/.openclaw/extensions/tracectrl && npm install && npm run build
```

## Configuration

Add to your `openclaw.json`:

```json
{
  "plugins": { "allow": ["tracectrl"] },
  "plugins.entries": {
    "tracectrl": {
      "enabled": true,
      "config": {
        "endpoint": "http://localhost:4318",
        "serviceName": "openclaw-gateway",
        "captureContent": true
      }
    }
  }
}
```

### Config options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `endpoint` | string | `http://localhost:4318` | OTLP collector endpoint |
| `serviceName` | string | `openclaw-gateway` | Service name for traces |
| `captureContent` | boolean | `false` | Capture message text and tool I/O (privacy-sensitive) |
| `protocol` | `"http"` \| `"grpc"` | `"http"` | OTLP transport protocol |
| `traces` | boolean | `true` | Enable trace export |
| `metrics` | boolean | `true` | Enable metric export |
| `metricsIntervalMs` | number | `30000` | Metric export interval |
| `headers` | object | `{}` | Additional HTTP headers for the OTLP exporter |

## Development

```bash
cd plugins/openclaw-tracectrl
npm install
npm run dev    # watch mode
```

## Architecture

```
src/
  index.ts      — Plugin entry point (definePluginEntry)
  config.ts     — Configuration parsing and defaults
  telemetry.ts  — OpenTelemetry provider setup (traces + metrics)
  hooks.ts      — Hook registrations (api.on + api.registerHook)
  security.ts   — Security detection helpers
```

The plugin is strictly observational — all hooks return `undefined` to avoid modifying gateway behavior. Every hook handler is wrapped in try/catch so telemetry errors never crash the gateway.

## License

Apache-2.0
