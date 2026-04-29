"""Core Guardrail class — framework-agnostic.

A Guardrail bundles: a judge LLM, a prompt template, decision policy, and
metadata. It knows how to evaluate a single (input or output) string and
emit a `tracectrl.guardrail.evaluation` OTEL span as a child of the
currently-active span.

This module deliberately does NOT import Strands; binding lives in
`strands_hook.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from tracectrl.guardrails.judge import JudgeResult, invoke_judge

OnViolation = Literal["log", "block"]
Timing = Literal["post_output", "pre_input"]
Severity = Literal["low", "medium", "high", "critical"]

_GUARDRAIL_SPAN_NAME = "tracectrl.guardrail.evaluation"


@dataclass
class Guardrail:
    """Declarative guardrail. Pass a list of these to `wrap_agent_with_guardrails`."""

    name: str
    description: str
    judge_prompt: str  # must contain `{output}` (or `{input}` for pre_input timing)
    judge_llm: Any  # opaque; expected to be a Strands BedrockModel or compatible
    on_violation: OnViolation = "log"
    timing: Timing = "post_output"
    severity: Severity = "medium"
    # Tracer is lazily acquired so import order doesn't matter.
    _tracer: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.on_violation == "block":
            # Defer full block semantics to v2; surface clearly at config time.
            raise NotImplementedError("block-on-violation deferred to v2")
        if self.timing not in ("post_output", "pre_input"):
            raise ValueError(f"invalid timing: {self.timing}")

    def _tracer_lazy(self):
        if self._tracer is None:
            self._tracer = trace.get_tracer("tracectrl.guardrails")
        return self._tracer

    def evaluate(self, text: str, agent_id: str | None = None, agent_name: str | None = None) -> JudgeResult:
        """Run the judge against `text` and emit a guardrail evaluation span.

        The span is started inside the context of the current active span,
        so it links naturally to the agent run span the engine will scan.
        `agent_id` / `agent_name` are stamped on the span so the engine can
        attribute the violation back to the right agent in the Alerts UI.
        """
        tracer = self._tracer_lazy()
        # Format judge prompt; support both {output} and {input} placeholders.
        prompt = self.judge_prompt
        for key in ("output", "input"):
            placeholder = "{" + key + "}"
            if placeholder in prompt:
                prompt = prompt.replace(placeholder, text)

        judge_model_name = _model_identifier(self.judge_llm)

        # Child of current span by default — start_as_current_span uses the
        # active context, which is what we want here.
        with tracer.start_as_current_span(_GUARDRAIL_SPAN_NAME) as span:
            span.set_attribute("tracectrl.guardrail.name", self.name)
            span.set_attribute("tracectrl.guardrail.judge_model", judge_model_name)
            span.set_attribute("tracectrl.guardrail.severity", self.severity)
            span.set_attribute("tracectrl.guardrail.timing", self.timing)
            span.set_attribute(
                "tracectrl.guardrail.evaluated_at",
                datetime.now(timezone.utc).isoformat(),
            )
            # Engine reads tracectrl.agent.id off the eval span to populate
            # `agent_id` on the violation row. Without these the Alerts UI
            # can't link a violation back to its agent.
            if agent_id:
                span.set_attribute("tracectrl.agent.id", agent_id)
            if agent_name:
                span.set_attribute("tracectrl.agent.name", agent_name)

            try:
                result = invoke_judge(self.judge_llm, prompt)
            except Exception as exc:  # noqa: BLE001 — judge errors must not crash agent
                span.set_attribute("tracectrl.guardrail.decision", "error")
                span.set_attribute("tracectrl.guardrail.reason", f"judge invocation failed: {exc}")
                span.set_attribute("tracectrl.guardrail.evidence", "")
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                # Treat errors as pass to avoid spamming false positives.
                return JudgeResult(passed=True, reason=f"judge error: {exc}", evidence=None)

            decision = "pass" if result.passed else "fail"
            span.set_attribute("tracectrl.guardrail.decision", decision)
            span.set_attribute("tracectrl.guardrail.reason", result.reason or "")
            span.set_attribute("tracectrl.guardrail.evidence", result.evidence or "")
            return result


def _model_identifier(judge_llm: Any) -> str:
    """Best-effort extraction of a stable model identifier for the span."""
    for attr in ("model_id", "model", "name"):
        val = getattr(judge_llm, attr, None)
        if isinstance(val, str) and val:
            return val
    # Some Strands models expose a config object.
    cfg = getattr(judge_llm, "config", None)
    if cfg is not None:
        for attr in ("model_id", "model"):
            val = getattr(cfg, attr, None)
            if isinstance(val, str) and val:
                return val
    return type(judge_llm).__name__
