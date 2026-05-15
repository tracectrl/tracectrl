"""Strands binding for guardrails.

Strands does not (yet) expose a stable, public post-output hook in its agent
lifecycle; the OpenInference processor only emits spans, it doesn't dispatch
callbacks. So we wrap the agent's `__call__` method directly: run the agent,
capture its response, then evaluate each guardrail in order. This keeps the
core `Guardrail` class framework-agnostic and isolates the Strands knowledge
to this file.

Two correctness details that bit us before:

  - **Post-output evals run on a background thread.** Strands' `__call__`
    is sync-on-the-surface but internally uses `run_async` (a fresh
    ThreadPoolExecutor + asyncio.run per call). If we evaluate the judge
    synchronously after `super().__call__()` returns, the agent caller
    blocks on the judge round-trip (2–8s for Gemini preview models with
    `response_schema`). To the user it looks like the agent "stops" after
    producing output. We fire-and-forget the eval onto a bounded executor,
    re-attaching the captured OTel context in the worker so the span lands
    under the same agent invocation. Pre-input stays sync — semantically
    must run before the agent fires.

  - **Snapshot the eval text BEFORE submitting.** The eval text builder
    reads `agent.messages`, which Strands mutates on subsequent calls.
    Without a snapshot, a fast follow-up prompt would race the bg thread
    and the judge would see a half-mutated history.
"""

from __future__ import annotations

import atexit
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Iterable, List

from opentelemetry import context as otel_context
from opentelemetry import trace

from tracectrl.guardrails.guardrail import Guardrail, _model_identifier

logger = logging.getLogger(__name__)


_REGISTRATION_SPAN_NAME = "tracectrl.guardrail.registered"
_INVOCATION_SPAN_NAME = "tracectrl.agent.invocation"


# Bounded executor for post-output evals. max_workers=2 keeps memory + FD
# usage tight; the queue is unbounded but in practice a single agent caller
# can't outpace 2 workers by much (judge calls are 1–8s each). Daemon
# threads so a hung judge doesn't block process exit. atexit shuts it down
# with a short grace period so short scripts still flush their spans.
_eval_executor: ThreadPoolExecutor | None = None


def _get_eval_executor() -> ThreadPoolExecutor:
    global _eval_executor
    if _eval_executor is None:
        _eval_executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="tracectrl-guardrail-eval",
        )
        atexit.register(_shutdown_eval_executor)
    return _eval_executor


def _shutdown_eval_executor() -> None:
    global _eval_executor
    if _eval_executor is not None:
        # wait=True so a script that runs `agent(...)` then exits still
        # flushes the eval span. Workers are bounded, so worst case we
        # wait one judge round-trip per pending eval.
        _eval_executor.shutdown(wait=True)
        _eval_executor = None


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

        tracer = trace.get_tracer("tracectrl.guardrails")

        # Outer span wraps the entire invocation. Strands' run_async copies
        # the OTel context into its worker thread, so the invoke_agent /
        # chat / tool spans Strands creates become children of this span.
        # The bg-thread post-eval re-attaches this same context, so its
        # eval span also lands here. Net result: one tidy tree per call.
        with tracer.start_as_current_span(_INVOCATION_SPAN_NAME) as invocation_span:
            if a_id:
                invocation_span.set_attribute("tracectrl.agent.id", a_id)
            if a_name:
                invocation_span.set_attribute("tracectrl.agent.name", a_name)

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
                # Snapshot the eval text NOW, while we still hold the lock
                # of the current invocation — a follow-up agent call would
                # mutate `agent.messages` and racing the bg worker against
                # that mutation is what produces the "memory leak between
                # agents" symptom users have reported.
                output_text = _build_eval_text(self, response)
                captured_ctx = otel_context.get_current()
                for g in post:
                    try:
                        _get_eval_executor().submit(
                            _run_post_eval_bg,
                            g,
                            output_text,
                            a_id,
                            a_name,
                            captured_ctx,
                        )
                    except Exception:  # noqa: BLE001 — never break the agent
                        logger.exception(
                            "guardrail %s failed to submit post_output eval", g.name
                        )

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


def _run_post_eval_bg(
    guardrail: Guardrail,
    output_text: str,
    agent_id: str | None,
    agent_name: str | None,
    captured_ctx: otel_context.Context,
) -> None:
    """Run a single post-output guardrail evaluation on a background thread.

    Re-attaches the OTel context captured at submit time so the eval span
    parents under the same agent invocation, not under whatever happened to
    be active in this worker. Errors are logged, never raised — this thread
    has no caller to surface them to.
    """
    token = otel_context.attach(captured_ctx)
    try:
        guardrail.evaluate(output_text, agent_id=agent_id, agent_name=agent_name)
    except Exception:  # noqa: BLE001
        logger.exception("guardrail %s raised during post_output eval", guardrail.name)
    finally:
        otel_context.detach(token)


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
