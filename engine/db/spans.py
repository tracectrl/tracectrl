"""Fetch spans from ClickHouse OTel exporter table.

The OTel Collector ClickHouse exporter writes to `otel_traces` with its own
fixed schema: Timestamp, TraceId, SpanId, SpanAttributes (Map), etc.
We extract tracectrl.* attributes from the SpanAttributes map.
"""

from engine.db.client import execute


def _system_prompt_from_messages(attrs: dict) -> str:
    """Fallback: scan llm.input_messages.N for a row whose role is 'system'.

    OpenInference's standard chat-instrumentation pattern emits each message
    as a flat `llm.input_messages.<i>.message.{role,content}` pair. Strands
    strips the system message before instrumenting (so this returns ''), but
    LangChain / Agno / many OpenAI wrappers include it. We scan up to 8 rows
    — the system message is conventionally row 0, but we tolerate non-zero
    placement for robustness.
    """
    for i in range(8):
        role = attrs.get(f"llm.input_messages.{i}.message.role")
        if not role:
            break
        if role == "system":
            return attrs.get(f"llm.input_messages.{i}.message.content", "")
    return ""


def fetch_all_spans() -> list[dict]:
    """Fetch all spans from the OTel exporter table. ReplacingMergeTree handles deduplication."""
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
        ORDER BY Timestamp ASC
        """
    )

    spans = []
    span_by_id = {}  # For building parent-child hierarchy
    for row in rows:
        attrs = row[10] if row[10] else {}  # SpanAttributes is a Map(String, String)

        # Extract nested metadata if present (from @ingress decorator)
        if "metadata" in attrs:
            try:
                import json
                metadata = json.loads(attrs["metadata"])
                # Merge metadata into attrs
                for key, value in metadata.items():
                    if key not in attrs:  # Don't override existing attrs
                        attrs[key] = str(value) if not isinstance(value, str) else value
            except (json.JSONDecodeError, TypeError):
                pass
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
            # NOTE: `llm.system` per OpenInference / OTel GenAI semconv is the
            # PROVIDER NAME ("anthropic", "strands-agents"), not the system
            # prompt. We keep it here for completeness but never use it as the
            # prompt source — see `tc_system_prompt` below.
            "llm_system": attrs.get("llm.system", ""),
            # System prompt — sourced in priority order:
            #   1. tracectrl.agent.system_prompt (set by tracectrl.tag_agent)
            #   2. fallback: a system-role row in llm.input_messages.N
            #      (some OpenInference instrumentors emit this; Strands does
            #      not as of 2026-04, but Agno and LangChain often do)
            "tc_system_prompt": (
                attrs.get("tracectrl.agent.system_prompt")
                or _system_prompt_from_messages(attrs)
                or ""
            ),
            "tool_name": (attrs.get("tool.name")
                          or attrs.get("openclaw.toolName")
                          or attrs.get("gen_ai.tool.name")
                          or ""),
            "tool_description": attrs.get("tool.description", ""),
            "tool_parameters": attrs.get("tool.parameters", ""),
            # TraceCtrl security fields from SpanAttributes map
            # Fall back to OpenInference/Agno attributes if tracectrl.* not set
            "tc_agent_id": (attrs.get("tracectrl.agent.id")
                            or attrs.get("agno.agent.id")
                            or attrs.get("agno.team.id")
                            or ""),
            "tc_agent_name": (attrs.get("tracectrl.agent.name")
                              or attrs.get("agent.name")
                              or ""),
            "tc_agent_role": attrs.get("tracectrl.agent.role", ""),
            "tc_agent_framework": attrs.get("tracectrl.agent.framework")
                                  or ("agno" if attrs.get("agno.agent.id")
                                      or attrs.get("agno.team.id") else ""),
            "tc_session_id": (attrs.get("tracectrl.session_id")
                              or attrs.get("session.id")
                              or ""),
            "tc_caller_agent_id": attrs.get("tracectrl.caller.agent_id", ""),
            "tc_input_source": attrs.get("tracectrl.input.source", ""),
            "tc_tool_category": attrs.get("tracectrl.tool.category", ""),
            "tc_tool_direction": attrs.get("tracectrl.tool.direction", ""),
            "tc_tool_target": attrs.get("tracectrl.tool.target", ""),
            "tc_memory_operation": attrs.get("tracectrl.memory.operation", ""),
            "tc_memory_store_id": attrs.get("tracectrl.memory.store_id", ""),
            "tc_system_prompt_hash": (
                attrs.get("tracectrl.agent.system_prompt_hash")
                or attrs.get("tracectrl.system_prompt_hash")
                or ""
            ),
            "tc_span_sequence": int(attrs.get("tracectrl.span_sequence", "0") or "0"),
            # Ingress detection
            "tc_ingress": attrs.get("tracectrl.ingress", "") == "True" or attrs.get("tracectrl.ingress", "") == "true",
            "tc_trigger_type": attrs.get("tracectrl.trigger_type", ""),
            # OpenClaw-specific attributes — prefer namespaced keys over bare keys
            # to avoid pollution from non-OpenClaw spans that use common attribute names
            "_oc_channel": attrs.get("openclaw.channel", "") or attrs.get("channel", ""),
            "_oc_provider": attrs.get("openclaw.provider", "") or attrs.get("provider", ""),
            "_oc_model": attrs.get("openclaw.model", "") or attrs.get("model", ""),
            "_oc_session_id": attrs.get("openclaw.sessionId", "") or attrs.get("sessionId", ""),
            "_oc_outcome": attrs.get("openclaw.outcome", "") or attrs.get("outcome", ""),
            "_oc_chat_id": attrs.get("openclaw.chatId", "") or attrs.get("chatId", ""),
            "_oc_trigger": attrs.get("openclaw.trigger", ""),
            "_gen_ai_request_model": attrs.get("gen_ai.request.model", ""),
        })

        # Index by span_id for parent-child lookup
        span_by_id[spans[-1]["span_id"]] = spans[-1]

    # Build parent-child map for delegation detection
    children_by_parent = {}
    for span in spans:
        parent_id = span["parent_span_id"]
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(span)

    # Post-process: derive agent identity from SpanName for frameworks
    # that don't set agent.name (e.g. Strands: "invoke_agent Foo")
    for span in spans:
        is_agent_span = span["oi_span_kind"] == "AGENT"
        # Also detect CHAIN spans with agent-like names (e.g. "payment_agent.execute")
        is_agent_chain = (span["oi_span_kind"] == "CHAIN"
                          and ".execute" in span["span_name"]
                          and "_agent" in span["span_name"].lower())
        if (is_agent_span or is_agent_chain) and not span["tc_agent_id"]:
            name = span["span_name"]
            if is_agent_chain:
                span["oi_span_kind"] = "AGENT"  # Promote to AGENT for pipeline
            if name.startswith("invoke_agent "):
                agent_name = name.replace("invoke_agent ", "")
            elif name.endswith(".run"):
                agent_name = name.replace(".run", "").replace("_", " ")
            elif name.endswith(".execute"):
                agent_name = name.replace(".execute", "").replace("_", " ")
            else:
                agent_name = name
            span["tc_agent_name"] = span["tc_agent_name"] or agent_name
            span["tc_agent_id"] = agent_name.lower().replace(" ", "-")
            # Detect framework from span naming pattern
            # Note: if agno.agent.id was present, tc_agent_framework was already
            # set to "agno" during initial extraction (lines 68-70) and won't reach here
            if not span["tc_agent_framework"]:
                if "invoke_agent" in name:
                    span["tc_agent_framework"] = "strands"
                elif is_agent_chain:
                    # CHAIN spans promoted to AGENT (e.g. "payment_agent.execute") are Strands agents
                    span["tc_agent_framework"] = "strands"
                else:
                    span["tc_agent_framework"] = "unknown"

    # Post-process: derive identity from OpenClaw gateway spans
    # OpenClaw uses openclaw.* span names with custom attributes
    for span in spans:
        name = span["span_name"]
        if not name.startswith("openclaw."):
            continue

        # OpenClaw emits events as a flat log (no parent context), so all
        # gateway-emitted spans get pinned to a single canonical agent:
        # "openclaw-gateway". Channel is preserved as span metadata.
        OC_AGENT_ID = "openclaw-gateway"
        OC_AGENT_NAME = "openclaw-gateway"

        if name in ("openclaw.model.usage", "openclaw.model.call"):
            span["oi_span_kind"] = "LLM"
            span["llm_model_name"] = (
                span["_oc_model"]
                or span.get("_gen_ai_request_model", "")
                or span["llm_model_name"]
            )
            span["tc_agent_framework"] = "openclaw"
            span["tc_agent_id"] = span["tc_agent_id"] or OC_AGENT_ID
            span["tc_agent_name"] = span["tc_agent_name"] or OC_AGENT_NAME

        elif name in ("openclaw.message.processed", "openclaw.run"):
            span["oi_span_kind"] = "AGENT"
            span["tc_agent_name"] = OC_AGENT_NAME
            span["tc_agent_id"] = OC_AGENT_ID
            span["tc_agent_framework"] = "openclaw"
            # Channel = ingress source (webchat / telegram / slack / ...).
            # OpenClaw doesn't set tracectrl.ingress, so derive it here.
            channel = span["_oc_channel"]
            if channel:
                span["tc_ingress"] = True
                span["tc_trigger_type"] = channel
                span["tc_input_source"] = "external"

        elif name in ("openclaw.tool.execution", "openclaw.exec"):
            span["oi_span_kind"] = "TOOL"
            # tool_name was already populated at extraction time from
            # tool.name / openclaw.toolName / gen_ai.tool.name fallbacks.
            if not span["tool_name"] and name == "openclaw.exec":
                span["tool_name"] = "exec"
            span["tc_tool_category"] = span["tc_tool_category"] or "primitive"
            span["tc_agent_framework"] = "openclaw"
            span["tc_agent_id"] = span["tc_agent_id"] or OC_AGENT_ID

        elif name == "openclaw.webhook.processed":
            span["oi_span_kind"] = "TOOL"
            channel = span["_oc_channel"]
            span["tool_name"] = f"webhook:{channel}" if channel else "webhook_handler"
            span["tc_tool_category"] = "external_api"
            span["tc_agent_framework"] = "openclaw"

        elif name == "openclaw.webhook.error":
            span["oi_span_kind"] = "TOOL"
            channel = span["_oc_channel"]
            span["tool_name"] = f"webhook:{channel}" if channel else "webhook_handler"
            span["status_code"] = "ERROR"
            span["tc_tool_category"] = "external_api"
            span["tc_agent_framework"] = "openclaw"

        elif name == "openclaw.session.stuck":
            span["oi_span_kind"] = "AGENT"
            span["tc_agent_name"] = "openclaw-session-monitor"
            span["tc_agent_id"] = "openclaw-session-monitor"
            span["tc_agent_framework"] = "openclaw"
            span["status_code"] = "ERROR"

        # Session ID from OpenClaw
        if not span["tc_session_id"]:
            span["tc_session_id"] = span["_oc_session_id"]

    # Post-process: Detect agent delegation wrappers
    # A TOOL span that has a child AGENT span is actually an agent delegation wrapper,
    # not a primitive tool. This handles the "agent-as-tool" pattern in Strands.
    for span in spans:
        if span["oi_span_kind"] == "TOOL":
            children = children_by_parent.get(span["span_id"], [])
            child_agents = [c for c in children if c["oi_span_kind"] == "AGENT"]

            if child_agents:
                # This tool spawned an agent → it's a delegation wrapper
                span["tc_tool_category"] = "agent_delegation"
                # Link to the delegated agent for topology visualization
                delegate = child_agents[0]  # Take first child agent
                span["tc_delegate_agent_id"] = delegate["tc_agent_id"]
                span["tc_delegate_agent_name"] = delegate["tc_agent_name"]
            elif not span["tc_tool_category"]:
                # No child agents → this is a genuine primitive tool
                span["tc_tool_category"] = "primitive"

    return spans
