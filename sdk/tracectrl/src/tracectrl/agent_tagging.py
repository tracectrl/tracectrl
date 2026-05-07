"""Framework-agnostic system-prompt tagging.

The TraceCtrl Agents page wants to show the system prompt of every agent it
discovers. Most popular agent frameworks (Strands, Agno, OpenClaw, raw OpenAI
agents) do not emit the system prompt as a span attribute — their OTEL
instrumentors only carry the user-facing message list. The system prompt is
held on the Agent object as a Python string and never leaves the process.

This module bridges that gap with a small registry + SpanProcessor pair:

  1. The user calls `tag_agent(agent, system_prompt=...)` once per agent.
     If `system_prompt` is omitted, the function introspects common Agent
     attributes (`system_prompt`, `system`, `instructions`).
  2. A `SystemPromptStamper` SpanProcessor is auto-installed by `configure()`.
     On every span start, it looks at the span name; if the name matches one
     of the known agent-run patterns (Strands `invoke_agent <Name>`, Agno
     `Agent.run`, OpenClaw `openclaw.run`, etc.), it consults the registry
     and stamps `tracectrl.agent.system_prompt` (and a 16-char SHA-256 hash)
     on the span.

The engine reads `tracectrl.agent.system_prompt` directly into the agent
inventory. A separate engine-side fallback scans `llm.input_messages.N` for
role=`system` rows so frameworks that DO emit the system message (some
OpenInference instrumentors) work without needing this helper.

Idempotent: re-tagging an agent updates the registered prompt.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from typing import Any, Optional

from opentelemetry.sdk.trace import SpanProcessor

logger = logging.getLogger(__name__)

# --- Module state -----------------------------------------------------------

# (agent_name, agent_id) -> system_prompt
_REGISTRY: dict[str, str] = {}
_REGISTRY_LOCK = threading.Lock()
_PROCESSOR_INSTALLED = False

# Span-name patterns that identify "this is the agent's run span". Strands +
# OpenClaw + Agno all follow stable naming conventions; for unknown frameworks
# the user can still benefit by passing a custom `span_name_match` to
# `tag_agent` (added in v2 if needed).
_KNOWN_PATTERNS: list[tuple[str, str]] = [
    ("invoke_agent ", "strands"),  # Strands: "invoke_agent <Name>"
    ("openclaw.run", "openclaw"),  # OpenClaw root
]


def _hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def _normalize_id(name: str) -> str:
    return name.lower().replace(" ", "-").replace("_", "-")


# --- Public API -------------------------------------------------------------


def tag_agent(agent: Any, system_prompt: Optional[str] = None) -> Any:
    """Register `agent`'s system prompt so it lands on the agent's run spans.

    Parameters
    ----------
    agent
        Any framework agent object exposing a `name` (or class name fallback).
    system_prompt
        The system prompt string. If omitted, the function tries to read it
        from the agent: `system_prompt`, `system`, then `instructions`. If
        none of those exist, the call is a no-op and a debug-log line is
        written.

    Returns
    -------
    The same agent (so tag_agent can be chained).
    """
    if system_prompt is None:
        for attr in ("system_prompt", "system", "instructions"):
            val = getattr(agent, attr, None)
            if isinstance(val, str) and val.strip():
                system_prompt = val
                break
    if not system_prompt:
        logger.debug("tag_agent: no system_prompt found on %r; skipping", agent)
        return agent

    name = getattr(agent, "name", None) or type(agent).__name__
    if not isinstance(name, str) or not name:
        logger.debug("tag_agent: cannot resolve agent name on %r; skipping", agent)
        return agent

    agent_id = _normalize_id(name)
    with _REGISTRY_LOCK:
        # Map by both display name (Strands span pattern) and lower-cased id
        # so the stamper can match either form without retrying every variant.
        _REGISTRY[name] = system_prompt
        _REGISTRY[agent_id] = system_prompt
    logger.debug("tag_agent: registered prompt for %s (%d chars)", name, len(system_prompt))
    return agent


def tag_agents(*agents: Any, **named: str) -> None:
    """Bulk variant — tag a sequence of agents (auto-introspect) or a mapping.

    Examples
    --------
    >>> tag_agents(orchestrator, docai, payment)        # auto-introspect
    >>> tag_agents(my_agent="You are a careful auditor.")
    """
    for a in agents:
        tag_agent(a)
    for name, prompt in named.items():
        # Treat the kwarg key as the agent name; build a minimal stand-in.
        with _REGISTRY_LOCK:
            _REGISTRY[name] = prompt
            _REGISTRY[_normalize_id(name)] = prompt


def _lookup(span_name: str) -> Optional[str]:
    """Return the registered prompt for the given span, if any."""
    if not span_name:
        return None
    # Strands: "invoke_agent <Name>"
    if span_name.startswith("invoke_agent "):
        agent_name = span_name[len("invoke_agent "):].strip()
        return _REGISTRY.get(agent_name) or _REGISTRY.get(_normalize_id(agent_name))
    # OpenClaw: single canonical gateway agent
    if span_name == "openclaw.run":
        return _REGISTRY.get("openclaw-gateway")
    # Generic: span name matches a registered name directly
    return _REGISTRY.get(span_name) or _REGISTRY.get(_normalize_id(span_name))


# --- SpanProcessor ----------------------------------------------------------


class SystemPromptStamper(SpanProcessor):
    """Stamps `tracectrl.agent.system_prompt` onto agent-run spans.

    Reads from the in-process registry populated by `tag_agent`. Runs in
    `on_start` so the attribute exists on the span before any exporter sees
    it. No-op for spans that don't match a known agent-run pattern.
    """

    def on_start(self, span, parent_context=None):  # type: ignore[override]
        try:
            if not span.is_recording():
                return
            prompt = _lookup(span.name)
            if not prompt:
                return
            span.set_attribute("tracectrl.agent.system_prompt", prompt)
            span.set_attribute("tracectrl.agent.system_prompt_hash", _hash_prompt(prompt))
        except Exception:
            # Tagging is best-effort — never break a span over it.
            logger.debug("SystemPromptStamper: failed to stamp %s", span.name, exc_info=True)

    def on_end(self, span):  # type: ignore[override]
        # Read-only ReadableSpan at end; we already stamped on_start.
        pass

    def shutdown(self):  # type: ignore[override]
        pass

    def force_flush(self, timeout_millis: int = 30000):  # type: ignore[override]
        return True


def _ensure_processor_installed(tracer_provider) -> None:
    """Idempotent install of SystemPromptStamper on the given TracerProvider."""
    global _PROCESSOR_INSTALLED
    if _PROCESSOR_INSTALLED:
        return
    try:
        tracer_provider.add_span_processor(SystemPromptStamper())
        _PROCESSOR_INSTALLED = True
        logger.debug("SystemPromptStamper installed on TracerProvider")
    except Exception:
        logger.warning("Could not install SystemPromptStamper", exc_info=True)
