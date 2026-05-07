# TraceCtrl SDK

Security observability for agentic AI systems. TraceCtrl instruments your AI agents with OpenTelemetry, scans for security misconfigurations, and streams violations in real time to the TraceCtrl dashboard.

## Install

```bash
pip install tracectrl
```

## Quickstart

```python
from tracectrl import init, tag_agent

# Initialize — sends traces to your TraceCtrl engine
init(endpoint="http://localhost:4317")

# Tag an agent with its system prompt for identity tracking
tag_agent("my-agent", system_prompt="You are a helpful assistant.")
```

## Guardrails

```python
from tracectrl.guardrails import register_guardrail, GuardrailAction

register_guardrail(
    agent_id="my-agent",
    name="no-exfiltration",
    action=GuardrailAction.BLOCK,
    description="Block attempts to send data to external endpoints",
)
```

## Links

- [Docs](https://tracectrl.io/docs)
- [Dashboard](https://tracectrl.io)
- [GitHub](https://github.com/tracectrl/tracectrl)
