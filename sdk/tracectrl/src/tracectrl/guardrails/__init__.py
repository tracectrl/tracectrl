"""TraceCtrl Guardrails — declarative judge-LLM checks on agent outputs.

Public API:
    Guardrail — declare a guardrail (name, judge LLM, prompt, severity).
    wrap_agent_with_guardrails — attach guardrails to a Strands Agent.
    register_guardrails — emit registration spans without wrapping (rare).
"""

from tracectrl.guardrails.guardrail import Guardrail
from tracectrl.guardrails.strands_hook import (
    wrap_agent_with_guardrails,
    register_guardrails,
)

__all__ = [
    "Guardrail",
    "wrap_agent_with_guardrails",
    "register_guardrails",
]
