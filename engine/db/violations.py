"""Guardrail violation ingestion + read for the alerts pipeline.

Picks up `tracectrl.guardrail.evaluation` OTEL spans (decision=fail) and persists
them to the `guardrail_violations` ReplacingMergeTree table. Deduplication is
handled by ClickHouse via ORDER BY (observed_at, violation_id), where
`violation_id` is the guardrail evaluation span_id.
"""

import json
import logging
from datetime import datetime
from engine.db.client import as_utc, execute

logger = logging.getLogger(__name__)


_VALID_SEVERITIES = {"low", "medium", "high", "critical"}
_VALID_DECISIONS = {"pass", "fail", "error"}


def update_violations(spans: list[dict]) -> None:
    """Scan OTel spans for guardrail evaluations with decision=fail and insert
    them into `guardrail_violations`.

    The `spans` parameter is accepted for signature parity with the rest of the
    pipeline (e.g. `update_topology(spans)`), but the raw guardrail.* span
    attributes are not preserved in the normalized span dict produced by
    `fetch_all_spans()`. We therefore pull them from `otel_traces` directly,
    which is also where the OTel collector writes them.

    Idempotent: ReplacingMergeTree dedupes on (observed_at, violation_id) and
    `violation_id == eval_span_id`, so re-processing the same span on every
    pipeline tick is a no-op.
    """
    # Watermark: only scan otel_traces newer than the latest already-ingested
    # violation. ReplacingMergeTree would dedupe re-inserts at read time, but
    # without this every pipeline tick scans all guardrail spans ever emitted
    # and writes N duplicate rows that the merge engine has to clean up.
    # 5-minute lookback covers any clock skew between OTel collector inserts
    # into otel_traces and our previous pipeline run.
    cutoff_rows = execute(
        "SELECT max(observed_at) FROM guardrail_violations FINAL"
    )
    cutoff = None
    if cutoff_rows and cutoff_rows[0][0]:
        candidate = cutoff_rows[0][0]
        # Same epoch-underflow trap as guardrail_registry: max() on empty
        # ReplacingMergeTree returns 1970-01-01 (not NULL), and INTERVAL
        # arithmetic on that underflows DateTime64. Treat as "no cutoff".
        if candidate.year > 1970:
            cutoff = candidate

    # The TraceCtrl SDK packs custom tracectrl.* attributes inside a `metadata`
    # JSON blob. The decision attribute will live there, NOT as a flat
    # SpanAttribute, so we OR both forms in the filter to be safe. We accept
    # both 'fail' (a guardrail flagged) and 'error' (transport/judge failed)
    # because the health-override pass below relies on error rows being
    # ingested into guardrail_violations to flip a guardrail's health to
    # 'error' in the registry.
    decision_filter = (
        "(SpanAttributes['tracectrl.guardrail.decision'] IN ('fail', 'error') "
        " OR JSONExtractString(SpanAttributes['metadata'], 'tracectrl.guardrail.decision') IN ('fail', 'error'))"
    )
    if cutoff:
        rows = execute(
            f"""
            SELECT Timestamp, TraceId, SpanId, ParentSpanId, SpanAttributes
            FROM otel_traces
            WHERE SpanName = 'tracectrl.guardrail.evaluation'
              AND {decision_filter}
              AND Timestamp > %(cutoff)s - INTERVAL 5 MINUTE
            """,
            {"cutoff": cutoff},
        )
    else:
        rows = execute(
            f"""
            SELECT Timestamp, TraceId, SpanId, ParentSpanId, SpanAttributes
            FROM otel_traces
            WHERE SpanName = 'tracectrl.guardrail.evaluation'
              AND {decision_filter}
            """
        )

    if not rows:
        logger.info("update_violations: no failing guardrail spans to ingest")
        return

    now = datetime.utcnow()
    inserts = []
    for ts, trace_id, span_id, parent_span_id, attrs in rows:
        attrs = dict(attrs or {})
        # Merge metadata-packed attrs back into the flat dict.
        if "metadata" in attrs:
            try:
                extra = json.loads(attrs["metadata"])
                for k, v in extra.items():
                    if k not in attrs:
                        attrs[k] = str(v) if not isinstance(v, str) else v
            except (json.JSONDecodeError, TypeError):
                pass

        eval_span_id = span_id
        agent_run_span_id = parent_span_id or eval_span_id

        decision = (attrs.get("tracectrl.guardrail.decision") or "fail").lower()
        if decision not in _VALID_DECISIONS:
            decision = "fail"

        severity = (attrs.get("tracectrl.guardrail.severity") or "medium").lower()
        if severity not in _VALID_SEVERITIES:
            severity = "medium"

        # Same Strands "default" agent_id quirk as the registry — synthesize
        # from name when unset/default so the ID joins with topology nodes.
        agent_id = attrs.get("tracectrl.agent.id", "")
        if agent_id in ("", "default"):
            name = attrs.get("tracectrl.agent.name", "")
            if name:
                agent_id = name.lower().replace(" ", "-").replace("_", "-")

        # Protector Plus violations carry tracectrl.guardrail.provider set
        # by the SDK; existing judge-LLM violations don't have it. Default to
        # judge_llm so the rows already in the table stay consistent with the
        # ALTER ... DEFAULT 'judge_llm' applied at schema-ensure time.
        provider = (attrs.get("tracectrl.guardrail.provider") or "judge_llm").lower()

        inserts.append((
            eval_span_id,                                         # violation_id
            trace_id,                                             # trace_id
            agent_run_span_id,                                    # span_id
            eval_span_id,                                         # eval_span_id
            agent_id,                                             # agent_id
            attrs.get("tracectrl.guardrail.name", ""),            # guardrail_name
            attrs.get("tracectrl.guardrail.judge_model", ""),     # judge_model
            decision,                                             # decision
            attrs.get("tracectrl.guardrail.reason", ""),          # reason
            attrs.get("tracectrl.guardrail.evidence", ""),        # evidence
            severity,                                             # severity
            ts,                                                   # observed_at
            now,                                                  # inserted_at
            provider,                                             # provider
        ))

    logger.info(f"update_violations: inserting {len(inserts)} guardrail violations")
    # Explicit column list — the ALTER added `provider` at the end of the
    # table, but being explicit protects against future column-order drift.
    execute(
        """INSERT INTO guardrail_violations
           (violation_id, trace_id, span_id, eval_span_id, agent_id,
            guardrail_name, judge_model, decision, reason, evidence,
            severity, observed_at, inserted_at, provider)
           VALUES""",
        inserts,
    )


# Column list MUST stay in lock-step with `_SELECT_COL_NAMES`. The names
# tuple is what `_row_to_violation` uses to unpack, eliminating the
# fragile-magic-index pattern that bit us when we added `provider`.
_SELECT_COL_NAMES = (
    "violation_id", "trace_id", "span_id", "eval_span_id", "agent_id",
    "guardrail_name", "judge_model", "decision", "reason", "evidence",
    "severity", "observed_at", "provider",
)
_SELECT_COLS = ", ".join(_SELECT_COL_NAMES)


def _row_to_violation(row: tuple) -> dict:
    """Unpack a `_SELECT_COLS` row into a dict by NAME, not by index.

    Without this, adding/reordering columns silently corrupts every consumer
    of the violations API — the SSE watermark index was a literal `row[12]`
    that would have swallowed a re-introduced `provider` column drift.
    """
    out = dict(zip(_SELECT_COL_NAMES, row))
    # ClickHouse-driver returns naive datetimes for DateTime64(..., 'UTC').
    # Pydantic + JS would then misinterpret the timestamp as local time;
    # stamping tz here is what makes the UI show local time correctly.
    out["observed_at"] = as_utc(out.get("observed_at"))
    return out


def get_violations(
    limit: int = 50,
    agent_id: str | None = None,
    severity: str | None = None,
) -> list[dict]:
    """Fetch recent violations ordered by observed_at DESC.

    Caps `limit` at 500. Optional filters on `agent_id` and `severity`.
    """
    limit = max(1, min(int(limit), 500))

    where_clauses = []
    params: dict = {"limit": limit}
    if agent_id:
        where_clauses.append("agent_id = %(agent_id)s")
        params["agent_id"] = agent_id
    if severity:
        sev = severity.lower()
        if sev in _VALID_SEVERITIES:
            where_clauses.append("severity = %(severity)s")
            params["severity"] = sev

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    rows = execute(
        f"""
        SELECT {_SELECT_COLS}
        FROM guardrail_violations FINAL
        {where_sql}
        ORDER BY observed_at DESC
        LIMIT %(limit)s
        """,
        params,
    )
    return [_row_to_violation(r) for r in rows]


def get_violations_since(since: datetime, limit: int = 100) -> list[dict]:
    """Fetch violations whose `inserted_at` is strictly greater than `since`.

    Used by the SSE stream to poll for newly inserted rows. Ordered by
    inserted_at ASC so the client receives them in arrival order.
    """
    limit = max(1, min(int(limit), 500))
    rows = execute(
        f"""
        SELECT {_SELECT_COLS}, inserted_at
        FROM guardrail_violations FINAL
        WHERE inserted_at > %(since)s
        ORDER BY inserted_at ASC
        LIMIT %(limit)s
        """,
        {"since": since, "limit": limit},
    )
    out = []
    for r in rows:
        v = _row_to_violation(r[: len(_SELECT_COL_NAMES)])
        # `inserted_at` is selected past `_SELECT_COLS` — pull it by
        # offset off the SAME source-of-truth length so adding columns
        # to `_SELECT_COL_NAMES` doesn't silently misread this field.
        v["_inserted_at"] = as_utc(r[len(_SELECT_COL_NAMES)])
        out.append(v)
    return out


def get_latest_inserted_at() -> datetime:
    """Return the largest inserted_at currently in the table, or epoch-ish if empty.

    Used as the starting watermark for an SSE subscriber so they don't get
    re-sent rows they already received via the initial `init` event.

    Returns tz-aware UTC. The SSE loop compares this against `_inserted_at`
    values from `get_violations_since` — those are now tz-aware too, and
    mixing naive + aware datetimes raises TypeError, so this must match.
    """
    from datetime import timezone

    rows = execute(
        "SELECT max(inserted_at) FROM guardrail_violations FINAL"
    )
    if rows and rows[0][0]:
        return as_utc(rows[0][0])
    return datetime(1970, 1, 1, tzinfo=timezone.utc)
