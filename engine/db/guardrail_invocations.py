"""Guardrail invocations read API — surfaces every `tracectrl.guardrail.evaluation`
span in `otel_traces` for a given (agent_id, guardrail_name).

This is intentionally different from `guardrail_violations`:
    - `guardrail_violations` is the dedup'd, pre-aggregated table of FAIL/ERROR
      decisions only. Populated by the pipeline tick. Used by the live SSE
      feed and the Alerts page.
    - This module reads ALL evaluation spans (pass + fail + error) directly
      from `otel_traces`, the way `guardrail_registry` reads registration
      spans. Used to power the "Recent Invocations" panel in the guardrail
      detail drawer — operators want to see the guardrail running, not just
      the violations it caught.

Querying otel_traces directly avoids a new persisted table for what is
effectively a derived view of existing spans. If this gets slow we can add
a materialized view later.
"""

import json
import logging
from datetime import datetime
from engine.db.client import as_utc, execute

logger = logging.getLogger(__name__)


def _merge_metadata(attrs: dict) -> dict:
    """The SDK packs custom tracectrl.* attributes inside a `metadata` JSON
    blob to keep OTel attribute counts low. Merge them back into the flat
    dict so downstream code can read by attribute name."""
    out = dict(attrs or {})
    if "metadata" in out:
        try:
            extra = json.loads(out["metadata"])
            for k, v in extra.items():
                if k not in out:
                    out[k] = str(v) if not isinstance(v, str) else v
        except (json.JSONDecodeError, TypeError):
            pass
    return out


def _row_to_invocation(ts: datetime, trace_id: str, span_id: str, attrs: dict) -> dict:
    """Turn a raw otel_traces row into the API response shape."""
    a = _merge_metadata(attrs)
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "observed_at": as_utc(ts),
        "decision": (a.get("tracectrl.guardrail.decision") or "").lower() or "pass",
        "timing": a.get("tracectrl.guardrail.timing") or "",
        "reason": a.get("tracectrl.guardrail.reason") or "",
        "evidence": a.get("tracectrl.guardrail.evidence") or "",
        "severity": (a.get("tracectrl.guardrail.severity") or "medium").lower(),
        "provider": (a.get("tracectrl.guardrail.provider") or "judge_llm").lower(),
        "judge_model": a.get("tracectrl.guardrail.judge_model") or "",
        # response_json is Protector-Plus specific — empty for legacy
        # judge_llm spans, which is fine.
        "response_json": a.get("tracectrl.guardrail.response_json") or "",
    }


def get_guardrail_invocations(
    agent_id: str,
    guardrail_name: str,
    limit: int = 50,
) -> list[dict]:
    """Return the most recent `tracectrl.guardrail.evaluation` spans for the
    given (agent_id, guardrail_name) — pass + fail + error decisions, ordered
    by Timestamp DESC. `limit` is clamped to [1, 200].

    Filters in SQL where possible; for `agent_id`/`guardrail_name` we have to
    match on either the flat SpanAttribute OR the JSON-packed metadata blob
    because the SDK uses metadata-packing. Same pattern as
    `update_guardrail_registry` and `update_violations`.
    """
    limit = max(1, min(int(limit), 200))

    # Match the agent_id from either the flat attr OR the packed metadata.
    # Same for the guardrail name. The dual-match is unavoidable until the
    # SDK stops metadata-packing (which would be a breaking change).
    rows = execute(
        """
        SELECT Timestamp, TraceId, SpanId, SpanAttributes
        FROM otel_traces
        WHERE SpanName = 'tracectrl.guardrail.evaluation'
          AND (
            SpanAttributes['tracectrl.agent.id'] = %(agent_id)s
            OR JSONExtractString(SpanAttributes['metadata'], 'tracectrl.agent.id') = %(agent_id)s
            OR (
              SpanAttributes['tracectrl.agent.id'] IN ('', 'default')
              AND JSONExtractString(SpanAttributes['metadata'], 'tracectrl.agent.name') = %(agent_id_human)s
            )
          )
          AND (
            SpanAttributes['tracectrl.guardrail.name'] = %(guardrail_name)s
            OR JSONExtractString(SpanAttributes['metadata'], 'tracectrl.guardrail.name') = %(guardrail_name)s
          )
        ORDER BY Timestamp DESC
        LIMIT %(limit)s
        """,
        {
            "agent_id": agent_id,
            # Reverse the slugify pattern the registry uses, so an agent_id
            # of "finflow-ai" matches a span with agent.name="finflow ai" or
            # "finflow_ai". Cheap and covers the common cases.
            "agent_id_human": agent_id.replace("-", " "),
            "guardrail_name": guardrail_name,
            "limit": limit,
        },
    )

    return [_row_to_invocation(ts, tid, sid, attrs) for (ts, tid, sid, attrs) in rows]
