"""TraceCtrl Guards — Protector Plus integration.

Public API:
    with tracectrl.guard():
        verdict = tracectrl.check_input(user_msg)
        response = agent(user_msg)
        tracectrl.check_output(str(response))

Note on naming: the function is `guard()`, not `guardrails()`, because
`tracectrl.guardrails` is already a subpackage (the legacy in-SDK LLM-judge
guardrails). Importing the subpackage rebinds `tracectrl.guardrails` to the
module object, shadowing any function of the same name on the package
namespace. Using `guard()` sidesteps that collision.

What it does:
    - On context-manager entry: lazily fetches Protector Plus config from the
      engine, starts a single background poster thread, and emits seven
      `tracectrl.guardrail.registered` OpenTelemetry spans (one per Protector
      Plus guardrail) so the engine's existing registry pipeline picks them up.
    - `check_input` / `check_output`: POST to Protector Plus is fire-and-forget
      via the background thread; the call returns IMMEDIATELY with a verdict
      stub. When the POST response arrives, one
      `tracectrl.guardrail.evaluation` span is emitted per flagged sub-guardrail
      (decision='fail'); the engine's existing `update_violations()` pipeline
      then ingests them into `guardrail_violations` with `provider='protector_plus'`.

Design notes:
    - The SDK never blocks. The 1.6s LLM judge latency would otherwise stack on
      top of every LLM call. Tradeoff: the verdict object returned synchronously
      has `flagged=False`; callers that genuinely need a synchronous gate can
      call `verdict.wait(timeout=2.0)`.
    - Spans are emitted in the background thread under a manually-captured
      parent context — child of whatever span was active at the
      `check_input/output()` call site, so the trace tree is shaped correctly
      even though the spans appear after the POST returns.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger("tracectrl.protector")


# Maps Protector Plus's internal check names → the TraceCtrl guardrail.name
# we register and attribute violations to. Order is the canonical display
# order in the Settings UI.
PROTECTOR_GUARDRAILS = (
    "llm",
    "keyword",
    "regex",
    "pii",
    "vector",
    "content_moderation",
    "system_prompt_protection",
)

# Endpoint paths on the Protector Plus side (relative to the configured root).
_INPUT_PATH = "/apikey/api/protectorplus/v1/input-check"
_OUTPUT_PATH = "/apikey/api/protectorplus/v1/output-check"

# Engine HTTP base URL — where we fetch the config from. Derives from
# TRACECTRL_API_URL (preferred) or falls back to localhost:8000 which matches
# the default `docker compose` stack.
_DEFAULT_API_URL = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------


@dataclass
class GuardrailVerdict:
    """Result of a check_input/check_output call.

    Because the actual Protector Plus POST is fire-and-forget on a background
    thread, the fields below are stub values when the verdict is returned to
    the caller. `wait(timeout)` blocks until the background thread fills them
    in, or until the timeout expires — useful if a caller wants to gate on
    the result (despite the v1 'log only' positioning).
    """

    flagged: bool = False
    execution_time_ms: int | None = None
    scores: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    _done: threading.Event = field(default_factory=threading.Event, repr=False)

    def wait(self, timeout: float = 2.0) -> "GuardrailVerdict":
        """Block until the background POST completes or the timeout fires.

        Returns self so the caller can chain: `v = check_input(msg).wait()`.
        """
        self._done.wait(timeout=timeout)
        return self

    def __bool__(self) -> bool:
        """`if not check_input(msg):` is intentionally always-truthy in async
        mode — the SDK doesn't gate the LLM call. Users who want gating must
        call .wait() and check .flagged explicitly."""
        return True


# ---------------------------------------------------------------------------
# Background runner — singleton
# ---------------------------------------------------------------------------


@dataclass
class _Config:
    endpoint_url: str = ""
    api_key: str = ""
    enabled_guardrails: tuple[str, ...] = ()
    fetched_at: float = 0.0


class _ProtectorRunner:
    """Singleton — owns the background POST thread, config cache, and queue.

    Lifecycle:
        - `ensure_started()` is called by `guardrails()` context manager entry.
          It lazily fetches config (HTTP GET to engine) and starts the worker
          thread. Idempotent.
        - `submit(phase, msg, verdict, parent_ctx)` enqueues a single
          (input|output)-check.
        - Worker thread: pulls (verdict, phase, msg, parent_ctx) tuples,
          POSTs to Protector Plus with 2s timeout, attaches the parent_ctx
          before emitting evaluation spans so they land in the right trace.
    """

    _instance: "_ProtectorRunner | None" = None
    _instance_lock = threading.Lock()

    @classmethod
    def get(cls) -> "_ProtectorRunner":
        if cls._instance is not None:
            return cls._instance
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = _ProtectorRunner()
            return cls._instance

    # Config is re-fetched from the engine if the cached copy is older than
    # this. Lets operators toggle guardrails on/off in the Settings UI
    # without restarting every running agent — the change takes effect on
    # the next `guard()` entry that crosses the refresh threshold.
    _CONFIG_MAX_AGE_SECONDS = 60

    def __init__(self) -> None:
        self._config = _Config()
        self._config_lock = threading.Lock()
        self._queue: queue.Queue = queue.Queue(maxsize=1000)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        # _registered tracks (agent_id, guardrail_name) pairs that have
        # already had a registration span emitted in THIS process. We track
        # per-pair (not just per-agent) so enabling a new guardrail in the
        # Settings UI causes that one — and only that one — to register on
        # the next `guard()` entry, leaving the existing ones alone.
        self._registered: set[tuple[str, str]] = set()
        self._registered_lock = threading.Lock()
        self._tracer = trace.get_tracer("tracectrl.protector")

    # ------- public ----------------------------------------------------------

    def ensure_started(self) -> _Config:
        """Lazily start the worker thread + refresh stale config.

        Returns the current config snapshot. Refreshes from the engine if
        either the cache is older than `_CONFIG_MAX_AGE_SECONDS` or the
        worker thread isn't alive — so operators can toggle guardrails in
        the Settings UI and have running agents pick up the change within
        roughly a minute, without process restarts.

        ALL state checks (thread liveness, config age, refresh, spawn)
        happen inside `_config_lock`. The outer unsynchronised read of
        `self._thread` we had before could allow two concurrent callers to
        both observe a dead thread, both enter the lock sequentially, and
        the second one's stale read of the worker reference could spawn a
        duplicate worker. Single lock entry serialises the whole decision.
        """
        with self._config_lock:
            thread_dead = self._thread is None or not self._thread.is_alive()
            config_stale = (
                time.time() - self._config.fetched_at
                > self._CONFIG_MAX_AGE_SECONDS
            )
            if thread_dead or config_stale:
                self._refresh_config_locked()
            if thread_dead:
                self._stop.clear()
                self._thread = threading.Thread(
                    target=self._run,
                    name="tracectrl-protector-poster",
                    daemon=True,
                )
                self._thread.start()
        return self._config_snapshot()

    def submit_check(
        self,
        phase: str,
        message: str,
        verdict: GuardrailVerdict,
        parent_ctx: otel_context.Context,
        agent_id: str,
        agent_name: str,
    ) -> None:
        """Enqueue a check. Drops on overflow with a warning.

        Re-runs `ensure_started()` defensively so a crashed worker thread
        gets resurrected on the next check rather than silently swallowing
        verdicts forever.
        """
        self.ensure_started()
        try:
            self._queue.put_nowait(
                (phase, message, verdict, parent_ctx, agent_id, agent_name)
            )
        except queue.Full:
            logger.warning(
                "tracectrl.protector: queue full (>1000 pending), dropping %s check",
                phase,
            )
            verdict.error = "dropped: queue full"
            verdict._done.set()

    def register_guardrails_for(self, agent_id: str, agent_name: str) -> None:
        """Emit one `tracectrl.guardrail.registered` span per enabled
        Protector Plus guardrail. Idempotent per (agent_id, guardrail_name)
        within the process.

        Per-pair tracking lets a newly-enabled guardrail register on the
        next `guard()` entry without re-emitting spans for guardrails that
        were already on file. We also claim each pair only after deciding
        we'll emit, so an early call against an empty config doesn't
        permanently suppress later registrations.
        """
        cfg = self._config_snapshot()
        if not cfg.enabled_guardrails:
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        for guardrail_key in cfg.enabled_guardrails:
            pair = (agent_id, guardrail_key)
            # Atomic check-and-claim — prevents concurrent agents racing on
            # the same pair and emitting duplicate spans.
            with self._registered_lock:
                if pair in self._registered:
                    continue
                self._registered.add(pair)
            try:
                with self._tracer.start_as_current_span(
                    "tracectrl.guardrail.registered"
                ) as span:
                    span.set_attribute("tracectrl.agent.id", agent_id)
                    span.set_attribute("tracectrl.agent.name", agent_name)
                    span.set_attribute(
                        "tracectrl.guardrail.name", f"protector_plus.{guardrail_key}"
                    )
                    # Protector Plus guardrails all behave as monitoring-mode
                    # (no blocking in v1) at varying timings.
                    span.set_attribute(
                        "tracectrl.guardrail.severity",
                        _default_severity_for(guardrail_key),
                    )
                    span.set_attribute(
                        "tracectrl.guardrail.timing",
                        _default_timing_for(guardrail_key),
                    )
                    span.set_attribute("tracectrl.guardrail.mode", "monitoring")
                    span.set_attribute(
                        "tracectrl.guardrail.judge_model",
                        f"protector_plus:{guardrail_key}",
                    )
                    span.set_attribute(
                        "tracectrl.guardrail.description",
                        _description_for(guardrail_key),
                    )
                    span.set_attribute("tracectrl.guardrail.judge_prompt", "")
                    span.set_attribute("tracectrl.guardrail.registered_at", now_iso)
                    span.set_attribute("tracectrl.guardrail.health", "active")
                    span.set_attribute("tracectrl.guardrail.health_reason", "")
                    span.set_attribute("tracectrl.guardrail.provider", "protector_plus")
            except Exception:
                logger.debug(
                    "failed to emit protector_plus registration span for %s",
                    guardrail_key,
                    exc_info=True,
                )

    # ------- internals -------------------------------------------------------

    def _config_snapshot(self) -> _Config:
        with self._config_lock:
            return _Config(
                endpoint_url=self._config.endpoint_url,
                api_key=self._config.api_key,
                enabled_guardrails=self._config.enabled_guardrails,
                fetched_at=self._config.fetched_at,
            )

    def _refresh_config_locked(self) -> None:
        """Fetch Protector Plus config from the engine. Caller holds config_lock.

        When the set of enabled guardrails shrinks (operator disabled one in
        the Settings UI), prune the corresponding pairs from `_registered`.
        Without this, an enable → disable → enable cycle leaves the pair
        cached, suppressing the re-registration span on the second enable
        and producing a stale 'active' registry row that no longer matches
        what's running.
        """
        api_url = os.getenv("TRACECTRL_API_URL", _DEFAULT_API_URL).rstrip("/")
        url = f"{api_url}/api/v1/guardrails/protector-config/sdk"
        old_enabled = set(self._config.enabled_guardrails)
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            self._config = _Config(
                endpoint_url=(body.get("endpoint_url") or "").rstrip("/"),
                api_key=body.get("api_key") or "",
                enabled_guardrails=tuple(body.get("enabled_guardrails") or ()),
                fetched_at=time.time(),
            )
            if not self._config.endpoint_url or not self._config.api_key:
                logger.info(
                    "tracectrl.protector: no Protector Plus config in engine; "
                    "calls will no-op until configured via the Settings UI"
                )
        except Exception as e:  # noqa: BLE001
            # The engine may be down on startup. Don't crash the agent.
            logger.warning(
                "tracectrl.protector: could not fetch config from %s: %s. "
                "Protector Plus checks will no-op until next process start.",
                url,
                e,
            )
            self._config = _Config(fetched_at=time.time())
            # On fetch error, don't prune — we don't know the true state.
            return

        removed = old_enabled - set(self._config.enabled_guardrails)
        if removed:
            with self._registered_lock:
                self._registered = {
                    pair for pair in self._registered if pair[1] not in removed
                }

    def _run(self) -> None:
        """Worker loop — pull from queue, POST to Protector Plus, emit spans.

        Defensive: catch BaseException too. A `MemoryError` during JSON
        serialisation (Protector Plus check payloads can be large) was
        leaking past the `except Exception` and silently killing the
        worker, leaving the caller's verdict `_done` event un-set so any
        `.wait()` would hang for its full timeout. We catch, mark the
        verdict failed, and re-raise non-Exception BaseExceptions
        (KeyboardInterrupt, SystemExit) so shutdown signals still work.
        """
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue
            verdict = item[2] if len(item) > 2 else None
            try:
                phase, message, vrd, parent_ctx, agent_id, agent_name = item
                self._handle(phase, message, vrd, parent_ctx, agent_id, agent_name)
            except Exception:
                logger.exception("tracectrl.protector worker: unhandled error")
                if verdict is not None and not verdict._done.is_set():
                    verdict.error = "worker error"
                    verdict._done.set()
            except BaseException as exc:
                # Mark the in-flight verdict failed so callers don't hang
                # on .wait(), then re-raise so the runtime sees the
                # shutdown signal (KeyboardInterrupt/SystemExit/MemoryError).
                if verdict is not None and not verdict._done.is_set():
                    verdict.error = f"worker terminated: {type(exc).__name__}"
                    verdict._done.set()
                logger.error(
                    "tracectrl.protector worker: terminating on %s",
                    type(exc).__name__,
                )
                raise
            finally:
                self._queue.task_done()

    def _handle(
        self,
        phase: str,
        message: str,
        verdict: GuardrailVerdict,
        parent_ctx: otel_context.Context,
        agent_id: str,
        agent_name: str,
    ) -> None:
        cfg = self._config_snapshot()
        if not cfg.endpoint_url or not cfg.api_key:
            verdict.error = "no config"
            verdict._done.set()
            return

        path = _INPUT_PATH if phase == "input" else _OUTPUT_PATH
        url = cfg.endpoint_url + path
        payload = json.dumps({"message": message}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": cfg.api_key,
            },
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            verdict.error = f"HTTP {e.code} {e.reason}"
            verdict._done.set()
            self._emit_error_span(phase, agent_id, agent_name, parent_ctx, verdict.error)
            return
        except Exception as e:  # noqa: BLE001
            verdict.error = str(e)
            verdict._done.set()
            self._emit_error_span(phase, agent_id, agent_name, parent_ctx, verdict.error)
            return

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        verdict.flagged = bool(body.get("injection_detected"))
        verdict.execution_time_ms = elapsed_ms
        verdict.scores = body.get("checks") or {}
        verdict._done.set()

        # For every enabled sub-guardrail, emit one `guardrail.evaluation`
        # span. `decision='fail'` if the check flagged, `'pass'` otherwise.
        # This matches the legacy LLM-judge path (which always emits a span
        # per evaluation regardless of outcome) so trace trees stay legible
        # and the UI shows the guardrail ran on every relevant request, not
        # just on failures. The engine ingester only inserts fail/error
        # rows into `guardrail_violations` — pass rows live in otel_traces
        # only.
        for guardrail_key, check in (body.get("checks") or {}).items():
            if not isinstance(check, dict) or not check.get("enabled"):
                continue
            flagged = _is_check_flagged(guardrail_key, check)
            self._emit_evaluation_span(
                phase=phase,
                guardrail_key=guardrail_key,
                check=check,
                message=message,
                agent_id=agent_id,
                agent_name=agent_name,
                parent_ctx=parent_ctx,
                decision="fail" if flagged else "pass",
            )

    def _emit_evaluation_span(
        self,
        phase: str,
        guardrail_key: str,
        check: dict,
        message: str,
        agent_id: str,
        agent_name: str,
        parent_ctx: otel_context.Context,
        decision: str = "fail",
    ) -> None:
        """Emit a `tracectrl.guardrail.evaluation` span as a child of the
        captured parent context. `decision` is 'pass' or 'fail' depending on
        whether the sub-check flagged. The engine's update_violations()
        pipeline picks up fail/error rows and writes them to
        guardrail_violations; pass rows stay in otel_traces only."""
        token = otel_context.attach(parent_ctx)
        try:
            with self._tracer.start_as_current_span(
                "tracectrl.guardrail.evaluation"
            ) as span:
                span.set_attribute(
                    "tracectrl.guardrail.name", f"protector_plus.{guardrail_key}"
                )
                span.set_attribute("tracectrl.guardrail.decision", decision)
                span.set_attribute("tracectrl.guardrail.provider", "protector_plus")
                span.set_attribute(
                    "tracectrl.guardrail.judge_model",
                    f"protector_plus:{guardrail_key}",
                )
                span.set_attribute(
                    "tracectrl.guardrail.severity",
                    _default_severity_for(guardrail_key),
                )
                span.set_attribute(
                    "tracectrl.guardrail.timing",
                    "pre_input" if phase == "input" else "post_output",
                )
                span.set_attribute(
                    "tracectrl.guardrail.reason",
                    _reason_for(guardrail_key, check),
                )
                # Evidence is the message that triggered the check, truncated
                # to keep the OTel attribute size sane. The engine renders
                # this verbatim in the violation drawer.
                evidence = message if len(message) <= 2048 else message[:2048] + "…"
                span.set_attribute("tracectrl.guardrail.evidence", evidence)
                # Pack the per-check Protector Plus response so the UI can
                # render the full score breakdown (threshold, entities, etc.)
                # in the Invocations panel. Capped at 8KB — typical
                # Protector Plus check payloads are <1KB but PII responses
                # can carry long entity lists.
                try:
                    response_json = json.dumps(check, default=str)
                    if len(response_json) > 8000:
                        response_json = response_json[:8000] + "...[truncated]"
                    span.set_attribute("tracectrl.guardrail.response_json", response_json)
                except (TypeError, ValueError):
                    pass
                span.set_attribute(
                    "tracectrl.guardrail.evaluated_at",
                    datetime.now(timezone.utc).isoformat(),
                )
                span.set_attribute("tracectrl.agent.id", agent_id)
                span.set_attribute("tracectrl.agent.name", agent_name)
        finally:
            otel_context.detach(token)

    def _emit_error_span(
        self,
        phase: str,
        agent_id: str,
        agent_name: str,
        parent_ctx: otel_context.Context,
        error: str,
    ) -> None:
        """Emit a single decision='error' eval span so transient Protector Plus
        outages surface as a degraded-health signal in the UI rather than
        silently dropping checks."""
        token = otel_context.attach(parent_ctx)
        try:
            with self._tracer.start_as_current_span(
                "tracectrl.guardrail.evaluation"
            ) as span:
                span.set_attribute(
                    "tracectrl.guardrail.name", "protector_plus.transport"
                )
                span.set_attribute("tracectrl.guardrail.decision", "error")
                span.set_attribute("tracectrl.guardrail.provider", "protector_plus")
                span.set_attribute(
                    "tracectrl.guardrail.judge_model", "protector_plus:transport"
                )
                span.set_attribute("tracectrl.guardrail.severity", "medium")
                span.set_attribute(
                    "tracectrl.guardrail.timing",
                    "pre_input" if phase == "input" else "post_output",
                )
                span.set_attribute("tracectrl.guardrail.reason", error)
                span.set_attribute("tracectrl.guardrail.evidence", "")
                span.set_attribute("tracectrl.agent.id", agent_id)
                span.set_attribute("tracectrl.agent.name", agent_name)
                span.set_status(Status(StatusCode.ERROR, error))
        finally:
            otel_context.detach(token)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_check_flagged(guardrail_key: str, check: dict) -> bool:
    """Decide whether a single Protector Plus sub-check is flagged. The
    Protector Plus response shape varies per guardrail — e.g. `injection_detected`
    is the umbrella, but per-check we use:
        - llm:        score >= threshold
        - keyword:    detected == true
        - regex:      detected == true
        - pii:        detected == true
        - vector:     score is not None and score >= threshold (if present)
        - content_moderation: result == 'UNSAFE' or unsafe == true
        - system_prompt_protection: detected == true
    """
    if not isinstance(check, dict):
        return False
    if not check.get("enabled"):
        return False

    if guardrail_key == "llm":
        score = check.get("score")
        threshold = check.get("threshold", 0.7)
        return isinstance(score, (int, float)) and score >= threshold
    if guardrail_key == "vector":
        score = check.get("score")
        if score is None:
            return False
        threshold = check.get("threshold", 0.7)
        return isinstance(score, (int, float)) and score >= threshold
    if guardrail_key == "content_moderation":
        return bool(check.get("unsafe")) or check.get("result") == "UNSAFE"
    # keyword / regex / pii / system_prompt_protection
    return bool(check.get("detected"))


def _default_severity_for(guardrail_key: str) -> str:
    if guardrail_key in ("llm", "system_prompt_protection"):
        return "high"
    if guardrail_key in ("content_moderation", "pii"):
        return "high"
    return "medium"


def _default_timing_for(guardrail_key: str) -> str:
    # system_prompt_protection only runs on output; everything else is
    # registered as pre_input but can fire on either phase at runtime.
    if guardrail_key == "system_prompt_protection":
        return "post_output"
    return "pre_input"


def _description_for(guardrail_key: str) -> str:
    return {
        "llm": "Prompt injection scoring via Protector Plus LLM judge (llama4:scout).",
        "keyword": "Exact keyword/phrase blocklist match.",
        "regex": "Regex pattern match against configured patterns.",
        "pii": "NER-based PII detection (names, emails, phone numbers, IC/passport, credit cards).",
        "vector": "Semantic similarity to known injection patterns via bge-m3 + ChromaDB.",
        "content_moderation": "Harmful content classification via Qwen3Guard-4B.",
        "system_prompt_protection": "Detects LLM responses that leak the system prompt.",
    }.get(guardrail_key, "Protector Plus guardrail.")


def _reason_for(guardrail_key: str, check: dict) -> str:
    """Render a human-readable reason for the violation row."""
    if guardrail_key == "llm":
        score = check.get("score")
        threshold = check.get("threshold", 0.7)
        score_str = f"{score:.2f}" if isinstance(score, (int, float)) else str(score)
        return f"LLM judge score {score_str} ≥ threshold {threshold}"
    if guardrail_key == "pii":
        entities = check.get("entities") or []
        if entities:
            return f"PII detected: {', '.join(str(e) for e in entities[:5])}"
        return "PII detected"
    if guardrail_key == "keyword":
        matched = check.get("matched") or []
        return f"Keyword match: {', '.join(str(m) for m in matched[:5])}"
    if guardrail_key == "regex":
        matched = check.get("matched") or []
        return f"Regex match: {', '.join(str(m) for m in matched[:5])}"
    if guardrail_key == "content_moderation":
        category = check.get("category") or "UNSAFE"
        return f"Content moderation: {category}"
    if guardrail_key == "vector":
        score = check.get("score")
        return f"Vector similarity score {score:.2f}" if isinstance(score, (int, float)) else "Vector similarity hit"
    if guardrail_key == "system_prompt_protection":
        return "System prompt leakage detected in output."
    return "Protector Plus flag."


def _resolve_active_agent_identity() -> tuple[str, str]:
    """Pull the currently-active agent id/name off the active span.

    The Strands instrumentor stamps `agent.name` and TraceCtrl's own enricher
    stamps `tracectrl.agent.id`. If neither is present (e.g. someone called
    `check_input` outside an agent run), fall back to the service name from
    the TracerProvider resource.
    """
    span = trace.get_current_span()
    name = ""
    agent_id = ""
    if span is not None:
        attrs = getattr(span, "attributes", None) or {}
        name = (
            attrs.get("agent.name")
            or attrs.get("tracectrl.agent.name")
            or ""
        )
        agent_id = attrs.get("tracectrl.agent.id") or ""
    if not name:
        # Fallback: TracerProvider resource service.name
        try:
            provider = trace.get_tracer_provider()
            resource = getattr(provider, "resource", None)
            if resource is not None:
                name = resource.attributes.get("service.name", "")
        except Exception:
            pass
    name = name or "unknown-agent"
    if not agent_id or agent_id == "default":
        agent_id = name.lower().replace(" ", "-").replace("_", "-")
    return agent_id, name


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@contextmanager
def guard():
    """Open a Protector Plus / TraceCtrl Guards scope.

    On entry: fetches config from the engine, starts the background poster
    thread (idempotent), emits 7 registration spans so the engine's guardrail
    registry knows what guardrails this agent has enabled. On exit: no
    teardown — the background thread is a daemon and outlives the scope.
    """
    runner = _ProtectorRunner.get()
    runner.ensure_started()
    agent_id, agent_name = _resolve_active_agent_identity()
    runner.register_guardrails_for(agent_id, agent_name)
    try:
        yield
    finally:
        # No teardown — agent code may issue more checks after this scope
        # closes, and the worker thread is process-lifetime.
        pass


def check_input(message: str) -> GuardrailVerdict:
    """Queue an asynchronous input-check against Protector Plus.

    Returns a verdict stub IMMEDIATELY (fire-and-forget). The actual
    Protector Plus POST happens on a background thread; when its response
    arrives the verdict is populated and one `tracectrl.guardrail.evaluation`
    span is emitted per flagged sub-guardrail (engine then writes them to
    `guardrail_violations`).

    Callers that need to *gate* the LLM call on the result must do:
        v = tracectrl.check_input(prompt).wait(timeout=2.0)
        if v.flagged:
            return "blocked"
    """
    return _submit("input", message)


def check_output(message: str) -> GuardrailVerdict:
    """Queue an asynchronous output-check against Protector Plus. See
    `check_input` for semantics."""
    return _submit("output", message)


def _submit(phase: str, message: str) -> GuardrailVerdict:
    runner = _ProtectorRunner.get()
    runner.ensure_started()
    agent_id, agent_name = _resolve_active_agent_identity()
    verdict = GuardrailVerdict()
    # Capture the active OTel context at the call site so the worker thread
    # can re-attach it before emitting eval spans — without this, the spans
    # would land at the root of a fresh trace.
    parent_ctx = otel_context.get_current()
    runner.submit_check(phase, message, verdict, parent_ctx, agent_id, agent_name)
    return verdict
