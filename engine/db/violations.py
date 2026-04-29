"""Guardrail violation ingestion + read for the alerts pipeline.

Picks up `tracectrl.guardrail.evaluation` OTEL spans (decision=fail) and persists
them to the `guardrail_violations` ReplacingMergeTree table. Deduplication is
handled by ClickHouse via ORDER BY (observed_at, violation_id), where
`violation_id` is the guardrail evaluation span_id.
"""

import logging
from datetime import datetime
from engine.db.client import execute

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
        cutoff = cutoff_rows[0][0]

    if cutoff:
        rows = execute(
            """
            SELECT Timestamp, TraceId, SpanId, ParentSpanId, SpanAttributes
            FROM otel_traces
            WHERE SpanName = 'tracectrl.guardrail.evaluation'
              AND SpanAttributes['tracectrl.guardrail.decision'] = 'fail'
              AND Timestamp > %(cutoff)s - INTERVAL 5 MINUTE
            """,
            {"cutoff": cutoff},
        )
    else:
        rows = execute(
            """
            SELECT Timestamp, TraceId, SpanId, ParentSpanId, SpanAttributes
            FROM otel_traces
            WHERE SpanName = 'tracectrl.guardrail.evaluation'
              AND SpanAttributes['tracectrl.guardrail.decision'] = 'fail'
            """
        )

    if not rows:
        logger.info("update_violations: no failing guardrail spans to ingest")
        return

    now = datetime.utcnow()
    inserts = []
    for ts, trace_id, span_id, parent_span_id, attrs in rows:
        attrs = attrs or {}

        eval_span_id = span_id
        agent_run_span_id = parent_span_id or eval_span_id

        decision = (attrs.get("tracectrl.guardrail.decision") or "fail").lower()
        if decision not in _VALID_DECISIONS:
            decision = "fail"

        severity = (attrs.get("tracectrl.guardrail.severity") or "medium").lower()
        if severity not in _VALID_SEVERITIES:
            severity = "medium"

        inserts.append((
            eval_span_id,                                         # violation_id
            trace_id,                                             # trace_id
            agent_run_span_id,                                    # span_id
            eval_span_id,                                         # eval_span_id
            attrs.get("tracectrl.agent.id", ""),                  # agent_id
            attrs.get("tracectrl.guardrail.name", ""),            # guardrail_name
            attrs.get("tracectrl.guardrail.judge_model", ""),     # judge_model
            decision,                                             # decision
            attrs.get("tracectrl.guardrail.reason", ""),          # reason
            attrs.get("tracectrl.guardrail.evidence", ""),        # evidence
            severity,                                             # severity
            ts,                                                   # observed_at
            now,                                                  # inserted_at
        ))

    logger.info(f"update_violations: inserting {len(inserts)} guardrail violations")
    execute("INSERT INTO guardrail_violations VALUES", inserts)


def _row_to_violation(row: tuple) -> dict:
    return {
        "violation_id": row[0],
        "trace_id": row[1],
        "span_id": row[2],
        "eval_span_id": row[3],
        "agent_id": row[4],
        "guardrail_name": row[5],
        "judge_model": row[6],
        "decision": row[7],
        "reason": row[8],
        "evidence": row[9],
        "severity": row[10],
        "observed_at": row[11],
    }


_SELECT_COLS = (
    "violation_id, trace_id, span_id, eval_span_id, agent_id, "
    "guardrail_name, judge_model, decision, reason, evidence, severity, "
    "observed_at"
)


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
        v = _row_to_violation(r)
        v["_inserted_at"] = r[12]
        out.append(v)
    return out


def get_latest_inserted_at() -> datetime:
    """Return the largest inserted_at currently in the table, or epoch-ish if empty.

    Used as the starting watermark for an SSE subscriber so they don't get
    re-sent rows they already received via the initial `init` event.
    """
    rows = execute(
        "SELECT max(inserted_at) FROM guardrail_violations FINAL"
    )
    if rows and rows[0][0]:
        return rows[0][0]
    return datetime(1970, 1, 1)
