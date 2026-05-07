"""Strands binding for guardrails.

Strands does not (yet) expose a stable, public post-output hook in its agent
lifecycle; the OpenInference processor only emits spans, it doesn't dispatch
callbacks. So we wrap the agent's `__call__` method directly: run the agent,
capture its response, then evaluate each guardrail in order. This keeps the
core `Guardrail` class framework-agnostic and isolates the Strands knowledge
to this file.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable, List

from opentelemetry import trace

from tracectrl.guardrails.guardrail import Guardrail, _model_identifier

logger = logging.getLogger(__name__)


_REGISTRATION_SPAN_NAME = "tracectrl.guardrail.registered"


def _emit_registration_span(agent_id: str, agent_name: str, guardrail: Guardrail) -> None:
    """Emit a one-shot registration span so the engine can populate
    guardrail_registry before any violation has fired. Idempotent on the
    engine side (ReplacingMergeTree dedups on agent_id+guardrail_name)."""
    try:
        tracer = trace.get_tracer("tracectrl.guardrails")
        with tracer.start_as_current_span(_REGISTRATION_SPAN_NAME) as span:
            span.set_attribute("tracectrl.agent.id", agent_id)
            span.set_attribute("tracectrl.agent.name", agent_name)
            span.set_attribute("tracectrl.guardrail.name", guardrail.name)
            span.set_attribute("tracectrl.guardrail.severity", guardrail.severity)
            span.set_attribute("tracectrl.guardrail.timing", guardrail.timing)
            span.set_attribute(
                "tracectrl.guardrail.mode",
                "blocking" if guardrail.on_violation == "block" else "monitoring",
            )
            span.set_attribute(
                "tracectrl.guardrail.judge_model",
                _model_identifier(guardrail.judge_llm),
            )
            span.set_attribute("tracectrl.guardrail.description", guardrail.description or "")
            # Send the full judge prompt so the UI can render it on the
            # guardrail detail page. OTel attribute values can be large; we
            # send up to ~16KB which covers any realistic guardrail prompt.
            prompt = guardrail.judge_prompt or ""
            if len(prompt) > 16000:
                prompt = prompt[:16000] + "\n\n[... truncated ...]"
            span.set_attribute("tracectrl.guardrail.judge_prompt", prompt)
            span.set_attribute(
                "tracectrl.guardrail.registered_at",
                datetime.now(timezone.utc).isoformat(),
            )
            # Health is best-effort: we have no way to ping the judge LLM
            # without invoking it (which would cost a real API call). Mark
            # as 'active' on registration; the engine flips to 'error' when
            # a guardrail evaluation span carries decision='error' for that
            # (agent_id, guardrail_name) pair.
            span.set_attribute("tracectrl.guardrail.health", "active")
            span.set_attribute("tracectrl.guardrail.health_reason", "")
    except Exception:
        logger.debug("failed to emit guardrail registration span", exc_info=True)


def wrap_agent_with_guardrails(agent: Any, guardrails: Iterable[Guardrail]) -> Any:
    """Monkey-patch `agent.__call__` to run guardrails post-output.

    Returns the same agent instance (for chaining). Idempotent: calling twice
    on the same agent will re-wrap; we tag the wrapped method to skip double
    application.
    """
    rails: List[Guardrail] = list(guardrails)
    if not rails:
        return agent

    pre_rails = [g for g in rails if g.timing == "pre_input"]
    post_rails = [g for g in rails if g.timing == "post_output"]

    # Resolve the agent identity once so every eval span carries it.
    # Strands' Agent class has a default agent_id of "default" which is
    # useless for joining; treat it (and empty) as missing and derive
    # from the agent name instead.
    agent_name = getattr(agent, "name", None) or type(agent).__name__
    raw_id = getattr(agent, "agent_id", None)
    if raw_id and raw_id != "default":
        agent_id = raw_id
    elif isinstance(agent_name, str):
        agent_id = agent_name.lower().replace(" ", "-").replace("_", "-")
    else:
        agent_id = None

    # Idempotency: tag the agent's class so re-wrapping refreshes rails
    # instead of stacking class layers. Stash the live rails on the agent
    # instance so the dispatcher in __call__ can read the current set.
    cls = type(agent)
    if getattr(cls, "_tracectrl_guardrails_subclass", False):
        # Already wrapped — refresh rails on this instance and re-emit
        # registration spans (cheap, idempotent at the engine).
        agent._tracectrl_pre_rails = pre_rails  # type: ignore[attr-defined]
        agent._tracectrl_post_rails = post_rails  # type: ignore[attr-defined]
        agent._tracectrl_agent_id = agent_id  # type: ignore[attr-defined]
        agent._tracectrl_agent_name = agent_name  # type: ignore[attr-defined]
        for g in rails:
            _emit_registration_span(agent_id, agent_name, g)
        return agent

    # Emit a registration span per guardrail so the engine can populate
    # guardrail_registry before any violation fires.
    for g in rails:
        _emit_registration_span(agent_id, agent_name, g)

    # Stash rails on the instance — read at call time so future re-wraps
    # don't need to rebuild the subclass.
    agent._tracectrl_pre_rails = pre_rails  # type: ignore[attr-defined]
    agent._tracectrl_post_rails = post_rails  # type: ignore[attr-defined]
    agent._tracectrl_agent_id = agent_id  # type: ignore[attr-defined]
    agent._tracectrl_agent_name = agent_name  # type: ignore[attr-defined]

    # IMPORTANT: Python looks up __call__ on the TYPE, not the instance,
    # so `agent.__call__ = wrapped` doesn't intercept `agent(...)`. The
    # only correct way to intercept on a per-instance basis is to swap
    # the agent's __class__ to a dynamically-created subclass whose
    # __call__ wraps super().__call__.
    def _guarded_call(self, *args: Any, **kwargs: Any) -> Any:
        pre = getattr(self, "_tracectrl_pre_rails", []) or []
        post = getattr(self, "_tracectrl_post_rails", []) or []
        a_id = getattr(self, "_tracectrl_agent_id", None)
        a_name = getattr(self, "_tracectrl_agent_name", None)

        if pre:
            user_input = _extract_input(args, kwargs)
            if user_input is not None:
                for g in pre:
                    try:
                        g.evaluate(user_input, agent_id=a_id, agent_name=a_name)
                    except Exception:  # noqa: BLE001
                        logger.exception("guardrail %s raised during pre_input eval", g.name)

        response = super(GuardedAgent, self).__call__(*args, **kwargs)

        if post:
            # The agent's final response is often a terse status summary
            # ("Payment workflow complete.") that hides the actual content
            # we need to screen — tool inputs/outputs, OCR'd text from
            # session context, etc. Pull the full message history off the
            # Strands agent so the judge sees the COMPLETE picture, not just
            # the synthesized summary.
            output_text = _build_eval_text(self, response)
            for g in post:
                try:
                    g.evaluate(output_text, agent_id=a_id, agent_name=a_name)
                except Exception:  # noqa: BLE001 — never break the agent
                    logger.exception("guardrail %s raised during post_output eval", g.name)

        return response

    GuardedAgent = type(
        f"_TraceCtrlGuarded_{cls.__name__}",
        (cls,),
        {
            "__call__": _guarded_call,
            "_tracectrl_guardrails_subclass": True,
        },
    )
    agent.__class__ = GuardedAgent

    return agent


def register_guardrails(agent: Any, guardrails: Iterable[Guardrail]) -> None:
    """Emit registration spans without wrapping the agent.

    Use when you want guardrails to appear in the TraceCtrl UI as 'registered
    but not yet attached' — useful for staging declarations during config or
    for declarative agent definitions where wrapping happens elsewhere. For
    most cases, prefer `wrap_agent_with_guardrails` which both registers AND
    wires up the runtime evaluation.
    """
    rails = list(guardrails)
    if not rails:
        return
    agent_name = getattr(agent, "name", None) or type(agent).__name__
    agent_id = (
        getattr(agent, "agent_id", None)
        or (agent_name.lower().replace(" ", "-") if isinstance(agent_name, str) else None)
    )
    for g in rails:
        _emit_registration_span(agent_id, agent_name, g)


def _extract_input(args: tuple, kwargs: dict) -> str | None:
    """Best-effort: first positional string arg, else common kwarg names."""
    for a in args:
        if isinstance(a, str):
            return a
    for key in ("prompt", "input", "message", "query"):
        val = kwargs.get(key)
        if isinstance(val, str):
            return val
    return None


def _build_eval_text(agent: Any, response: Any) -> str:
    """Combine the agent's final response + the full message history into a
    single text blob the judge can scan.

    Strands agents often return a terse status summary that hides the
    interesting content (tool inputs, OCR'd text from session reads, etc.).
    The injection markers a guardrail wants to catch typically live in
    intermediate messages, not the final response. Pull `.messages` off the
    Strands Agent — it's a list of message dicts with `content` blocks of
    role text, tool_use, tool_result, etc. — and stringify everything we can
    find. Capped at 64KB so a giant history doesn't blow the judge prompt.
    """
    parts: list[str] = []
    final = _stringify_response(response)
    if final:
        parts.append(f"FINAL_RESPONSE:\n{final}")

    messages = getattr(agent, "messages", None)
    if isinstance(messages, list):
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "")
            content = msg.get("content")
            if isinstance(content, str):
                parts.append(f"[{role}] {content}")
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    # Bedrock content shapes: text, toolUse, toolResult.
                    if "text" in block and isinstance(block["text"], str):
                        parts.append(f"[{role}] {block['text']}")
                    elif "toolUse" in block:
                        tu = block["toolUse"]
                        name = tu.get("name", "?")
                        inp = tu.get("input", {})
                        parts.append(f"[{role} tool_use:{name}] {inp!s}")
                    elif "toolResult" in block:
                        tr = block["toolResult"]
                        for item in (tr.get("content") or []):
                            if isinstance(item, dict) and "text" in item:
                                parts.append(f"[tool_result] {item['text']}")

    blob = "\n\n".join(parts)
    if len(blob) > 64000:
        blob = blob[:64000] + "\n\n[... truncated ...]"
    return blob


def _stringify_response(response: Any) -> str:
    """Best-effort flattening of a Strands agent response into a single string."""
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    # Strands response objects commonly expose `.message` or `.output` or `.text`.
    for attr in ("text", "output_text", "message", "output", "content"):
        val = getattr(response, attr, None)
        if isinstance(val, str) and val:
            return val
        if isinstance(val, dict):
            # Bedrock-style: {"role": "...", "content": [{"text": "..."}]}
            content = val.get("content")
            if isinstance(content, list):
                parts = [c.get("text", "") for c in content if isinstance(c, dict)]
                joined = "".join(parts)
                if joined:
                    return joined
    return str(response)
