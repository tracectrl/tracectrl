"""Fetch spans from ClickHouse OTel exporter table.

The OTel Collector ClickHouse exporter writes to `otel_traces` with its own
fixed schema: Timestamp, TraceId, SpanId, SpanAttributes (Map), etc.
We extract tracectrl.* attributes from the SpanAttributes map.
"""

from datetime import datetime
from engine.db.client import execute


def fetch_new_spans(since: datetime) -> list[dict]:
    """Fetch all spans since the given timestamp from the OTel exporter table."""
    rows = execute(
        """
        SELECT
            Timestamp,
            TraceId,
            SpanId,
            ParentSpanId,
            SpanName,
            SpanKind,
            ServiceName,
            Duration,
            StatusCode,
            StatusMessage,
            SpanAttributes
        FROM otel_traces
        WHERE Timestamp > %(since)s
        ORDER BY Timestamp ASC
        """,
        {"since": since},
    )

    spans = []
    for row in rows:
        attrs = row[10] if row[10] else {}  # SpanAttributes is a Map(String, String)
        spans.append({
            "timestamp": row[0],
            "trace_id": row[1],
            "span_id": row[2],
            "parent_span_id": row[3],
            "span_name": row[4],
            "span_kind": row[5],
            "service_name": row[6],
            "duration_ns": row[7],
            "status_code": row[8],
            "status_message": row[9],
            # OpenInference fields from SpanAttributes map
            "oi_span_kind": attrs.get("openinference.span.kind", ""),
            "input_value": attrs.get("input.value", ""),
            "output_value": attrs.get("output.value", ""),
            "llm_model_name": attrs.get("llm.model_name", ""),
            "llm_system": attrs.get("llm.system", ""),
            "tool_name": attrs.get("tool.name", ""),
            "tool_description": attrs.get("tool.description", ""),
            "tool_parameters": attrs.get("tool.parameters", ""),
            # TraceCtrl security fields from SpanAttributes map
            "tc_agent_id": attrs.get("tracectrl.agent.id", ""),
            "tc_agent_name": attrs.get("tracectrl.agent.name", ""),
            "tc_agent_role": attrs.get("tracectrl.agent.role", ""),
            "tc_agent_framework": attrs.get("tracectrl.agent.framework", ""),
            "tc_session_id": attrs.get("tracectrl.session_id", ""),
            "tc_caller_agent_id": attrs.get("tracectrl.caller.agent_id", ""),
            "tc_input_source": attrs.get("tracectrl.input.source", ""),
            "tc_tool_category": attrs.get("tracectrl.tool.category", ""),
            "tc_tool_target": attrs.get("tracectrl.tool.target", ""),
            "tc_memory_operation": attrs.get("tracectrl.memory.operation", ""),
            "tc_memory_store_id": attrs.get("tracectrl.memory.store_id", ""),
            "tc_system_prompt_hash": attrs.get("tracectrl.system_prompt_hash", ""),
            "tc_span_sequence": int(attrs.get("tracectrl.span_sequence", "0") or "0"),
        })

    return spans
