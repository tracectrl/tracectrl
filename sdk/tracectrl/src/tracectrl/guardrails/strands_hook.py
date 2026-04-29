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
from typing import Any, Iterable, List

from tracectrl.guardrails.guardrail import Guardrail

logger = logging.getLogger(__name__)


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

    original_call = getattr(agent, "__call__", None)
    if original_call is None:
        raise TypeError(f"agent {type(agent).__name__} has no __call__ to wrap")

    # If already wrapped, replace the rails list rather than nesting wrappers.
    if getattr(original_call, "_tracectrl_guardrails_wrapped", False):
        original_call._tracectrl_rails = rails  # type: ignore[attr-defined]
        return agent

    # Resolve the agent identity once so every eval span carries it. We try
    # several common Strands attributes; the engine derives the same id from
    # the agent run span for join correctness.
    agent_name = getattr(agent, "name", None) or type(agent).__name__
    agent_id = (
        getattr(agent, "agent_id", None)
        or (agent_name.lower().replace(" ", "-") if isinstance(agent_name, str) else None)
    )

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        # pre_input: best-effort grab of the prompt from args/kwargs.
        if pre_rails:
            user_input = _extract_input(args, kwargs)
            if user_input is not None:
                for g in pre_rails:
                    try:
                        g.evaluate(user_input, agent_id=agent_id, agent_name=agent_name)
                    except Exception:  # noqa: BLE001
                        logger.exception("guardrail %s raised during pre_input eval", g.name)

        # Run the actual agent — invoking via the bound original method on the instance.
        response = original_call(*args, **kwargs)

        # post_output: stringify the response and evaluate.
        if post_rails:
            output_text = _stringify_response(response)
            for g in post_rails:
                try:
                    g.evaluate(output_text, agent_id=agent_id, agent_name=agent_name)
                except Exception:  # noqa: BLE001 — never break the agent
                    logger.exception("guardrail %s raised during post_output eval", g.name)

        return response

    wrapped._tracectrl_guardrails_wrapped = True  # type: ignore[attr-defined]
    wrapped._tracectrl_rails = rails  # type: ignore[attr-defined]

    # Bind to the instance so it overrides the class method for this agent only.
    try:
        agent.__call__ = wrapped  # type: ignore[method-assign]
    except (AttributeError, TypeError):
        # Some Strands Agent classes use __call__ via __class__ lookup; fall back
        # to attaching as `invoke`/`run` if those exist.
        for alt in ("invoke", "run"):
            if hasattr(agent, alt):
                setattr(agent, alt, wrapped)
                break
        else:
            raise

    return agent


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
