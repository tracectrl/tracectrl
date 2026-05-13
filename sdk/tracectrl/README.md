# TraceCtrl SDK

Security observability and runtime guardrails for agentic AI. TraceCtrl instruments your agents with OpenTelemetry, captures every LLM call and tool invocation as security-enriched spans, and streams the trace + guardrail violations to the TraceCtrl dashboard in real time.

## Install

```bash
pip install tracectrl
```

For framework integrations:

```bash
pip install tracectrl-instrumentation-strands   # AWS Strands
pip install tracectrl-instrumentation-agno      # Agno
```

## Quickstart

```python
import tracectrl
from tracectrl.instrumentation.strands import StrandsInstrumentor

# Configure once at startup — points the SDK at your TraceCtrl engine
tracectrl.configure(
    service_name="my-agent",
    endpoint="http://localhost:4317",
)

# Auto-instrument Strands (or replace with the instrumentor for your framework)
StrandsInstrumentor().instrument()

# Your existing agent code — no changes needed
```

## Guardrails

Two guardrail providers, designed to coexist on the same agent:

**1. Built-in LLM judge** — declarative guardrails evaluated by a Bedrock model:

```python
from tracectrl.guardrails import Guardrail, wrap_agent_with_guardrails

no_pii_leak = Guardrail(
    name="no_pii_leak",
    description="Block agent responses containing personally identifiable info.",
    judge_prompt="Does the following response contain PII?\n\n{output}",
    judge_llm=bedrock_model,
    severity="high",
)

wrap_agent_with_guardrails(my_agent, [no_pii_leak])
```

**2. TraceCtrl Guards (Protector Plus)** — explicit checks against an external LLM firewall covering prompt injection, PII, content moderation, vector similarity, keywords/regex, and system-prompt leakage:

```python
import tracectrl

with tracectrl.guard():
    tracectrl.check_input(user_message)
    response = my_agent(user_message)
    tracectrl.check_output(str(response))
```

Configure the Protector Plus endpoint and per-domain API key in the TraceCtrl dashboard's Settings page. Calls are async fire-and-forget — they emit OpenTelemetry evaluation spans without blocking the LLM call. Both decisions (`pass` / `fail`) show up in the trace tree and the dashboard's Guardrails page, with failures streamed as live alerts.

## Tagging agents

```python
from tracectrl import tag_agent

tag_agent(my_agent)   # reads agent.system_prompt + agent.name automatically
```

Identity shows up on the dashboard's Agents page.

## Links

- [Documentation](https://docs.tracectrl.ai)
- [Dashboard](https://tracectrl.ai)
- [GitHub](https://github.com/tracectrl/tracectrl)
