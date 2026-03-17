"""Session and span queries against the otel_traces table."""

from engine.db.client import execute


def get_session_list() -> list[dict]:
    """Fetch recent traces grouped as sessions."""
    rows = execute(
        """
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
                SpanAttributes['tracectrl.agent.name'],
                Timestamp,
                SpanAttributes['tracectrl.agent.name'] != ''
            )                                                        AS agent_name,
            maxIf(1, StatusCode = 'STATUS_CODE_ERROR')               AS has_error
        FROM otel_traces
        WHERE TraceId != ''
        GROUP BY TraceId
        ORDER BY start_time DESC
        LIMIT 200
        """
    )

    columns = [
        "trace_id", "start_time", "end_time", "total_duration_ns",
        "span_count", "root_span_name", "root_span_id", "agent_name", "has_error",
    ]
    result = []
    for row in rows:
        d = dict(zip(columns, row))
        d["has_error"] = bool(d["has_error"])
        d["root_span_name"] = d["root_span_name"] or "unknown"
        d["root_span_id"] = d["root_span_id"] or ""
        d["agent_name"] = d["agent_name"] or ""
        result.append(d)
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
