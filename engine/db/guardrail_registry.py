"""Guardrail registry ingestion + read.

Picks up `tracectrl.guardrail.registered` OTel spans (emitted once per
guardrail per process via the SDK's strands_hook on registration) and persists
them to `guardrail_registry`. ReplacingMergeTree dedupes on
(agent_id, guardrail_name) using `last_seen_at` as the version column, so
re-emitting the same registration just refreshes the row.
"""

import logging
from datetime import datetime
from engine.db.client import execute

logger = logging.getLogger(__name__)


_VALID_SEVERITIES = {"low", "medium", "high", "critical"}
_VALID_MODES = {"monitoring", "blocking"}
_VALID_TIMINGS = {"post_output", "pre_input"}
_VALID_HEALTH = {"active", "error", "disabled"}


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        # Handle trailing Z
        v = value.replace("Z", "+00:00") if value.endswith("Z") else value
        dt = datetime.fromisoformat(v)
        # ClickHouse DateTime64 with UTC tz expects naive UTC or aware; strip tz to naive UTC.
        if dt.tzinfo is not None:
            dt = dt.astimezone(tz=None).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def update_guardrail_registry(spans: list[dict]) -> None:
    """Scan OTel spans for guardrail registrations and upsert into the registry.

    The `spans` parameter is accepted for signature parity with the rest of
    the pipeline but the raw guardrail.* span attributes aren't preserved in
    the normalized span dict produced by `fetch_all_spans()`. We pull them
    from `otel_traces` directly, with the same watermark pattern as
    `update_violations` so we don't rescan the world on every tick.

    After the registration upsert, run a side-update that flips health to
    'error' for any (agent_id, guardrail_name) that has had a decision=error
    violation in the last hour.
    """
    cutoff_rows = execute(
        "SELECT max(last_seen_at) FROM guardrail_registry FINAL"
    )
    cutoff = None
    if cutoff_rows and cutoff_rows[0][0]:
        cutoff = cutoff_rows[0][0]

    if cutoff:
        rows = execute(
            """
            SELECT Timestamp, SpanAttributes
            FROM otel_traces
            WHERE SpanName = 'tracectrl.guardrail.registered'
              AND Timestamp > %(cutoff)s - INTERVAL 5 MINUTE
            """,
            {"cutoff": cutoff},
        )
    else:
        rows = execute(
            """
            SELECT Timestamp, SpanAttributes
            FROM otel_traces
            WHERE SpanName = 'tracectrl.guardrail.registered'
            """
        )

    if not rows:
        logger.info("update_guardrail_registry: no registration spans to ingest")
    else:
        now = datetime.utcnow()
        # Dedupe within this batch on (agent_id, guardrail_name) — keep the
        # most recent span per key so we don't insert N near-identical rows
        # that ReplacingMergeTree then has to merge.
        latest: dict[tuple[str, str], tuple] = {}
        for ts, attrs in rows:
            attrs = attrs or {}
            agent_id = attrs.get("tracectrl.agent.id", "")
            guardrail_name = attrs.get("tracectrl.guardrail.name", "")
            if not agent_id or not guardrail_name:
                continue

            severity = (attrs.get("tracectrl.guardrail.severity") or "medium").lower()
            if severity not in _VALID_SEVERITIES:
                severity = "medium"

            mode = (attrs.get("tracectrl.guardrail.mode") or "monitoring").lower()
            if mode not in _VALID_MODES:
                mode = "monitoring"

            timing = (attrs.get("tracectrl.guardrail.timing") or "post_output").lower()
            if timing not in _VALID_TIMINGS:
                timing = "post_output"

            health = (attrs.get("tracectrl.guardrail.health") or "active").lower()
            if health not in _VALID_HEALTH:
                health = "active"

            registered_at = _parse_iso(
                attrs.get("tracectrl.guardrail.registered_at", "")
            ) or ts

            row = (
                agent_id,
                guardrail_name,
                severity,
                mode,
                timing,
                attrs.get("tracectrl.guardrail.judge_model", ""),
                attrs.get("tracectrl.guardrail.description", ""),
                health,
                attrs.get("tracectrl.guardrail.health_reason", ""),
                registered_at,
                ts,             # last_seen_at = span Timestamp
                now,            # inserted_at
            )
            key = (agent_id, guardrail_name)
            existing = latest.get(key)
            if existing is None or row[10] > existing[10]:
                latest[key] = row

        inserts = list(latest.values())
        if inserts:
            logger.info(
                "update_guardrail_registry: inserting %d registry rows",
                len(inserts),
            )
            execute("INSERT INTO guardrail_registry VALUES", inserts)

    # Health override pass: any (agent_id, guardrail_name) with decision=error
    # in the last hour gets health='error' with the most recent error reason.
    try:
        _apply_error_health_overrides()
    except Exception:
        logger.exception("update_guardrail_registry: error-health override failed")


def _apply_error_health_overrides() -> None:
    """Re-insert registry rows with health='error' for any guardrail that had
    a decision=error violation in the past hour. Best-effort — leaves all
    other fields intact by reading the current registry row first.
    """
    error_rows = execute(
        """
        SELECT
            v.agent_id,
            v.guardrail_name,
            argMax(v.reason, v.observed_at) AS latest_reason,
            count() AS error_count
        FROM guardrail_violations FINAL AS v
        WHERE v.decision = 'error'
          AND v.observed_at > now() - INTERVAL 1 HOUR
        GROUP BY v.agent_id, v.guardrail_name
        """
    )
    if not error_rows:
        return

    # Build a lookup of latest error info keyed by (agent_id, guardrail_name).
    error_lookup: dict[tuple[str, str], str] = {}
    for agent_id, guardrail_name, latest_reason, _ in error_rows:
        if agent_id and guardrail_name:
            error_lookup[(agent_id, guardrail_name)] = latest_reason or "guardrail evaluation error"

    if not error_lookup:
        return

    # Pull the existing registry rows for these keys so we can preserve the
    # rest of the columns when we flip health.
    keys_clause = ", ".join(
        ["(%(a{0})s, %(g{0})s)".format(i) for i in range(len(error_lookup))]
    )
    params: dict = {}
    for i, (agent_id, guardrail_name) in enumerate(error_lookup.keys()):
        params[f"a{i}"] = agent_id
        params[f"g{i}"] = guardrail_name

    existing = execute(
        f"""
        SELECT
            agent_id, guardrail_name, severity, mode, timing,
            judge_model, description, health, health_reason,
            registered_at, last_seen_at
        FROM guardrail_registry FINAL
        WHERE (agent_id, guardrail_name) IN ({keys_clause})
        """,
        params,
    )
    if not existing:
        return

    now = datetime.utcnow()
    inserts = []
    for (agent_id, guardrail_name, severity, mode, timing,
         judge_model, description, _health, _health_reason,
         registered_at, last_seen_at) in existing:
        reason = error_lookup.get((agent_id, guardrail_name))
        if reason is None:
            continue
        inserts.append((
            agent_id,
            guardrail_name,
            severity,
            mode,
            timing,
            judge_model,
            description,
            "error",
            reason,
            registered_at,
            last_seen_at,
            now,
        ))

    if inserts:
        logger.info(
            "update_guardrail_registry: applying error-health override to %d rows",
            len(inserts),
        )
        execute("INSERT INTO guardrail_registry VALUES", inserts)


_SELECT_COLS = (
    "agent_id, guardrail_name, severity, mode, timing, "
    "judge_model, description, health, health_reason, "
    "registered_at, last_seen_at"
)


def _row_to_registration(row: tuple, recent_24h: int = 0) -> dict:
    return {
        "agent_id": row[0],
        "guardrail_name": row[1],
        "severity": row[2],
        "mode": row[3],
        "timing": row[4],
        "judge_model": row[5],
        "description": row[6],
        "health": row[7],
        "health_reason": row[8],
        "registered_at": row[9],
        "last_seen_at": row[10],
        "recent_activity_24h": recent_24h,
    }


def get_guardrail_registry(agent_id: str | None = None) -> list[dict]:
    """Return all guardrail registrations, optionally filtered by agent_id.

    Each row is annotated with `recent_activity_24h` — the count of matching
    rows in `guardrail_violations` whose observed_at > now() - 24h.
    Computed via a single grouped query joined with the registry, NOT one
    query per row.
    """
    where_sql = ""
    params: dict = {}
    if agent_id:
        where_sql = "WHERE agent_id = %(agent_id)s"
        params["agent_id"] = agent_id

    rows = execute(
        f"""
        SELECT {_SELECT_COLS}
        FROM guardrail_registry FINAL
        {where_sql}
        ORDER BY agent_id, guardrail_name
        """,
        params,
    )
    if not rows:
        return []

    activity_rows = execute(
        f"""
        SELECT v.agent_id, v.guardrail_name, count() AS c
        FROM guardrail_violations FINAL AS v
        WHERE v.observed_at > now() - INTERVAL 24 HOUR
          AND (v.agent_id, v.guardrail_name) IN (
              SELECT agent_id, guardrail_name
              FROM guardrail_registry FINAL
              {where_sql}
          )
        GROUP BY v.agent_id, v.guardrail_name
        """,
        params,
    )
    activity = {(r[0], r[1]): int(r[2]) for r in (activity_rows or [])}

    out = []
    for r in rows:
        recent = activity.get((r[0], r[1]), 0)
        out.append(_row_to_registration(r, recent))
    return out
