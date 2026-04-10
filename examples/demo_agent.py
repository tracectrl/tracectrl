"""TraceCtrl Demo Agent — sends test spans to verify your setup works.

Usage:
    python examples/demo_agent.py

Requires: docker compose up -d (TraceCtrl stack running)
"""

import tracectrl
from opentelemetry import trace

# Configure TraceCtrl
tracectrl.configure(
    service_name="demo-agent",
    endpoint="http://localhost:4317",
)

tracer = trace.get_tracer("demo-agent")

print("TraceCtrl Demo Agent")
print("=" * 40)

# Simulate an agent session with tool calls
with tracer.start_as_current_span("agent_run", attributes={
    "openinference.span.kind": "AGENT",
    "agent.name": "Demo Agent",
}) as agent_span:
    print("  → Agent started")

    # Simulate an LLM call
    with tracer.start_as_current_span("llm_call", attributes={
        "openinference.span.kind": "LLM",
        "llm.model_name": "demo-model",
        "input.value": "What is the weather today?",
        "output.value": "I'll check the weather for you using the weather tool.",
    }):
        print("  → LLM call: What is the weather today?")

    # Simulate a tool call
    with tracer.start_as_current_span("get_weather", attributes={
        "openinference.span.kind": "TOOL",
        "tool.name": "get_weather",
        "tool.description": "Get current weather for a location",
        "input.value": '{"location": "Singapore"}',
        "output.value": '{"temp": 31, "condition": "partly cloudy"}',
    }):
        print("  → Tool call: get_weather(Singapore)")

    # Simulate another LLM call with the result
    with tracer.start_as_current_span("llm_response", attributes={
        "openinference.span.kind": "LLM",
        "llm.model_name": "demo-model",
        "input.value": "Weather data: 31°C, partly cloudy",
        "output.value": "It's currently 31°C and partly cloudy in Singapore.",
    }):
        print("  → LLM response: 31°C, partly cloudy in Singapore")

print()
print("✓ 4 spans sent to TraceCtrl")
print()
print("Next steps:")
print("  → Dashboard:  http://localhost:3000")
print("  → Sessions:   http://localhost:3000/sessions")
print("  → Health:     tracectrl doctor")
