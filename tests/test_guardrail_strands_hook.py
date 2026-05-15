"""Tests for the Strands guardrail wrap — covers the fix for two bugs:

  1. Sync post-output judge blocked the caller; on Gemini judge it could
     stall the agent for several seconds and looked like the agent had
     "stopped". Post-output evals now run on a background thread.

  2. The eval span was being parented to whatever was active in the
     calling thread AFTER `super().__call__()` returned — by which time
     Strands' inner spans had already closed and run in a separate
     thread anyway. The wrap now opens a `tracectrl.agent.invocation`
     span so Strands' spans AND the bg-thread eval span share a stable
     parent.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

from tracectrl.guardrails.guardrail import Guardrail
from tracectrl.guardrails.strands_hook import (
    _shutdown_eval_executor,
    wrap_agent_with_guardrails,
)


class _FakeAgent:
    """Minimal stand-in for a Strands Agent — just needs `__call__`,
    `name`, and a `messages` list for `_build_eval_text` to read."""

    def __init__(self, name: str = "TestAgent", response: str = "ok"):
        self.name = name
        self.agent_id = "default"
        self.messages: list = []
        self._response = response

    def __call__(self, prompt, **kwargs):
        # Mimic Strands' behaviour: a call appends to `messages`. The bg
        # eval thread must snapshot BEFORE we mutate again, or the judge
        # sees cross-call contamination.
        self.messages.append({"role": "user", "content": [{"text": prompt}]})
        self.messages.append({"role": "assistant", "content": [{"text": self._response}]})
        return self._response


def _make_guardrail(eval_started: threading.Event, eval_done: threading.Event,
                   recorded: list, hold: threading.Event | None = None) -> Guardrail:
    """Build a Guardrail whose `evaluate` records what it saw and blocks on
    `hold` if provided — lets a test prove the agent caller did NOT block
    even though the judge is still in-flight."""
    g = Guardrail(
        name="test_guard",
        description="t",
        judge_prompt="check {output}",
        judge_llm=MagicMock(model_id="fake"),
        on_violation="log",
        timing="post_output",
        severity="low",
    )

    def fake_evaluate(text, agent_id=None, agent_name=None):
        eval_started.set()
        if hold is not None:
            hold.wait(timeout=5)
        recorded.append({"text": text, "agent_id": agent_id, "agent_name": agent_name})
        eval_done.set()

    g.evaluate = fake_evaluate  # type: ignore[method-assign]
    return g


def test_post_output_eval_does_not_block_agent_return():
    """The agent caller must return immediately; the judge runs on a bg
    thread. Asserted by holding the judge with an event and confirming
    the agent call returns before the event is released."""
    eval_started = threading.Event()
    eval_done = threading.Event()
    hold = threading.Event()
    recorded: list = []

    agent = _FakeAgent(response="agent says hello")
    g = _make_guardrail(eval_started, eval_done, recorded, hold=hold)
    wrap_agent_with_guardrails(agent, [g])

    t0 = time.perf_counter()
    result = agent("user prompt")
    elapsed = time.perf_counter() - t0

    # Agent returned in well under the hold timeout — proves non-blocking.
    assert elapsed < 1.0, f"agent call blocked for {elapsed:.2f}s — should be fire-and-forget"
    assert result == "agent says hello"

    # The bg eval has at least kicked off by now.
    assert eval_started.wait(timeout=2.0), "bg eval never started"

    # Let the bg eval finish so we can inspect what it saw.
    hold.set()
    assert eval_done.wait(timeout=2.0), "bg eval never finished after release"

    assert len(recorded) == 1
    assert "agent says hello" in recorded[0]["text"]
    assert recorded[0]["agent_name"] == "TestAgent"

    _shutdown_eval_executor()


def test_post_output_eval_text_snapshot_does_not_race_followup_call():
    """If a second prompt fires before the first prompt's bg eval reads
    `agent.messages`, the bg eval must still see prompt 1's history, not a
    half-mutated prompt 1+2 mix. This is the 'memory leak between agents'
    symptom — bg eval reading the agent's live `messages` mid-mutation.

    We hold the first prompt's eval mid-evaluate, fire a second prompt
    (which mutates `agent.messages`), then release the first eval. Its
    snapshot must NOT contain prompt-2 content.
    """
    eval1_started = threading.Event()
    eval1_done = threading.Event()
    hold_eval1 = threading.Event()
    recorded: list = []

    agent = _FakeAgent(response="response one")
    g = _make_guardrail(eval1_started, eval1_done, recorded, hold=hold_eval1)
    wrap_agent_with_guardrails(agent, [g])

    # Fire prompt 1 — bg eval will block at hold_eval1.
    agent("prompt one")
    assert eval1_started.wait(timeout=2.0)

    # While the bg eval is suspended, fire a second prompt that mutates
    # `agent.messages`. (No guard hold this time — we want messages to
    # change underneath the held bg thread.)
    agent._response = "response two"
    # Swap the guardrail's evaluate to a no-op so prompt 2's eval doesn't
    # also block. We're testing snapshot isolation for prompt 1's eval.
    g.evaluate = lambda text, agent_id=None, agent_name=None: None  # type: ignore
    agent("prompt two")

    # Now release prompt-1's bg eval. It should read the snapshot taken
    # BEFORE prompt 2 mutated `messages`.
    hold_eval1.set()
    assert eval1_done.wait(timeout=2.0)

    snapshot = recorded[0]["text"]
    assert "response one" in snapshot
    assert "prompt one" in snapshot
    # The critical assertion: snapshot must not contain prompt-2 content.
    assert "response two" not in snapshot
    assert "prompt two" not in snapshot

    _shutdown_eval_executor()
