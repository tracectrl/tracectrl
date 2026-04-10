"""Session and span queries against the otel_traces table."""

from datetime import timezone

from engine.db.client import execute


def get_session_list(service: str | None = None) -> list[dict]:
    """Fetch recent traces grouped as sessions."""
    service_filter = "AND ServiceName = %(service)s" if service else ""
    params = {"service": service} if service else None
    rows = execute(
        f"""
        SELECT
            TraceId,
            min(Timestamp)                                           AS start_time,
            max(Timestamp + toIntervalNanosecond(Duration))          AS end_time,
            max(toUnixTimestamp64Nano(Timestamp) + Duration)
                - min(toUnixTimestamp64Nano(Timestamp))              AS total_duration_ns,
            count()                                                  AS span_count,
            argMinIf(SpanName, Timestamp, ParentSpanId = '' OR ParentSpanId = '0000000000000000')
                                                                     AS root_span_name,
            argMinIf(SpanId,   Timestamp, ParentSpanId = '' OR ParentSpanId = '0000000000000000')
                                                                     AS root_span_id,
            argMinIf(
                if(SpanAttributes['tracectrl.agent.name'] != '',
                   SpanAttributes['tracectrl.agent.name'],
                   if(SpanAttributes['openclaw.channel'] != '',
                      concat('openclaw-', SpanAttributes['openclaw.channel']),
                      '')),
                Timestamp,
                SpanAttributes['tracectrl.agent.name'] != '' OR SpanAttributes['openclaw.channel'] != ''
            )                                                        AS agent_name,
            anyIf(
                SpanAttributes['openclaw.sessionKey'],
                SpanAttributes['openclaw.sessionKey'] != ''
            )                                                        AS openclaw_session_key,
            maxIf(1, StatusCode = 'STATUS_CODE_ERROR')               AS has_error
        FROM otel_traces
        WHERE TraceId != ''
          {service_filter}
        GROUP BY TraceId
        ORDER BY start_time DESC
        LIMIT 200
        """,
        params,
    )

    columns = [
        "trace_id", "start_time", "end_time", "total_duration_ns",
        "span_count", "root_span_name", "root_span_id", "agent_name",
        "openclaw_session_key", "has_error",
    ]
    parsed = []
    for row in rows:
        d = dict(zip(columns, row))
        d["has_error"] = bool(d["has_error"])
        d["root_span_name"] = d["root_span_name"] or "unknown"
        d["root_span_id"] = d["root_span_id"] or ""
        d["agent_name"] = d["agent_name"] or ""
        parsed.append(d)

    # ── Merge OpenClaw sessions that share the same sessionKey ──
    # OpenClaw emits a separate TraceId per span, so each appears as a
    # 1-span session.  We merge them into a single logical session keyed
    # by openclaw.sessionKey while keeping non-OpenClaw rows untouched.
    merged: dict[str, dict] = {}   # sessionKey -> merged row
    result: list[dict] = []
    for d in parsed:
        sk = d.get("openclaw_session_key") or ""
        if sk:
            if sk in merged:
                m = merged[sk]
                m["start_time"] = min(m["start_time"], d["start_time"])
                m["end_time"] = max(m["end_time"], d["end_time"])
                m["total_duration_ns"] = max(
                    m["total_duration_ns"], d["total_duration_ns"]
                )
                m["span_count"] += d["span_count"]
                m["has_error"] = m["has_error"] or d["has_error"]
                # Keep a list of all trace ids so the UI can fetch spans
                m["_trace_ids"].append(d["trace_id"])
            else:
                d["_trace_ids"] = [d["trace_id"]]
                merged[sk] = d
        else:
            result.append(d)

    # Finalise merged OpenClaw sessions
    for d in merged.values():
        # Recalculate total_duration_ns from merged window
        start_ns = int(d["start_time"].replace(tzinfo=timezone.utc).timestamp() * 1e9)
        end_ns = int(d["end_time"].replace(tzinfo=timezone.utc).timestamp() * 1e9)
        d["total_duration_ns"] = end_ns - start_ns
        # Store auxiliary trace ids so the detail view can fetch all spans
        d["extra_trace_ids"] = d.pop("_trace_ids")
        result.append(d)

    # Remove the internal-only key before returning
    for d in result:
        d.pop("openclaw_session_key", None)
        d.pop("_trace_ids", None)

    result.sort(key=lambda d: d["start_time"], reverse=True)
    return result


def get_trace_spans(trace_id: str) -> list[dict]:
    """Fetch all spans for a single trace, ordered by timestamp."""
    rows = execute(
        """
        SELECT
            SpanId,
            ParentSpanId,
            SpanName,
            SpanKind,
            ServiceName,
            toUnixTimestamp64Nano(Timestamp)    AS start_ns,
            Duration                            AS duration_ns,
            StatusCode,
            StatusMessage,
            SpanAttributes,
            ResourceAttributes
        FROM otel_traces
        WHERE TraceId = %(trace_id)s
        ORDER BY Timestamp ASC
        """,
        {"trace_id": trace_id},
    )

    columns = [
        "span_id", "parent_span_id", "span_name", "span_kind",
        "service_name", "start_ns", "duration_ns", "status_code",
        "status_message", "attributes", "resource_attributes",
    ]
    result = []
    for row in rows:
        d = dict(zip(columns, row))
        # ClickHouse Map returns dict; guard against None
        d["attributes"] = d["attributes"] or {}
        d["resource_attributes"] = d["resource_attributes"] or {}
        # Normalize root span marker
        if d["parent_span_id"] == "0000000000000000":
            d["parent_span_id"] = ""
        result.append(d)
    return result


def get_latest_trace_spans(service: str | None = None) -> list[dict]:
    """Fetch all spans from the most recent workflow run.

    Agno creates separate traces per agent.run(). To get the full
    workflow picture, we find the latest trace's start time, then
    fetch ALL traces that started within 5 minutes of it — these
    are part of the same workflow execution.
    """
    service_filter = "AND ServiceName = %(service)s" if service else ""
    anchor_params: dict = {}
    if service:
        anchor_params["service"] = service

    rows = execute(
        f"""
        SELECT min(Timestamp) AS latest_start
        FROM otel_traces
        WHERE TraceId IN (
            SELECT TraceId FROM otel_traces
            WHERE 1=1 {service_filter}
            ORDER BY Timestamp DESC LIMIT 1
        )
        """,
        anchor_params or None,
    )
    if not rows or not rows[0][0]:
        return []

    latest_start = rows[0][0]

    span_params: dict = {"start": latest_start}
    if service:
        span_params["service"] = service

    # Fetch all spans from traces that started within 5 min of the latest
    span_rows = execute(
        f"""
        SELECT
            SpanId,
            ParentSpanId,
            SpanName,
            SpanKind,
            ServiceName,
            toUnixTimestamp64Nano(Timestamp)    AS start_ns,
            Duration                            AS duration_ns,
            StatusCode,
            StatusMessage,
            SpanAttributes,
            ResourceAttributes
        FROM otel_traces
        WHERE Timestamp >= %(start)s - INTERVAL 5 MINUTE
          AND Timestamp <= %(start)s + INTERVAL 10 MINUTE
          {service_filter}
          AND TraceId IN (
            SELECT DISTINCT TraceId
            FROM otel_traces
            WHERE Timestamp >= %(start)s - INTERVAL 5 MINUTE
              AND Timestamp <= %(start)s + INTERVAL 5 MINUTE
              {service_filter}
        )
        ORDER BY Timestamp ASC
        """,
        span_params,
    )

    columns = [
        "span_id", "parent_span_id", "span_name", "span_kind",
        "service_name", "start_ns", "duration_ns", "status_code",
        "status_message", "attributes", "resource_attributes",
    ]
    result = []
    for row in span_rows:
        d = dict(zip(columns, row))
        d["attributes"] = d["attributes"] or {}
        d["resource_attributes"] = d["resource_attributes"] or {}
        if d["parent_span_id"] == "0000000000000000":
            d["parent_span_id"] = ""
        result.append(d)
    return result
