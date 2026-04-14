"""TraceCtrlSpanProcessor — enriches spans with security attributes."""

import hashlib
from contextvars import ContextVar
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from opentelemetry import trace as trace_api
from tracectrl import schema
from tracectrl.inference import infer_tool_category, infer_tool_direction, infer_trigger_type
from tracectrl.session import current_session_id

_span_sequence: ContextVar[int] = ContextVar("tracectrl_span_sequence", default=0)

# OpenInference / Agno attribute keys (set by framework instrumentors)
_OI_SPAN_KIND = "openinference.span.kind"
_OI_AGENT_NAME = "agent.name"
_AGNO_AGENT_ID = "agno.agent.id"
_AGNO_TEAM_ID = "agno.team.id"
_AGNO_SESSION_ID = "session.id"


class TraceCtrlSpanProcessor(SpanProcessor):
    """
    Enriches every span with tracectrl.* security attributes.
    Registered on the TracerProvider alongside the OpenInference instrumentor.
    """

    def on_start(self, span, parent_context=None):
        session_id = current_session_id()
        if session_id:
            span.set_attribute(schema.TC_SESSION_ID, session_id)

        # Auto-detect ingress: spans with no parent trace context
        if parent_context:
            span_context = trace_api.get_current_span(parent_context).get_span_context()
            if not span_context or not span_context.is_valid:
                # Root span - mark as ingress
                span.set_attribute(schema.TC_INGRESS, True)
                # Try to infer trigger type from span name
                trigger_type = infer_trigger_type(span.name if hasattr(span, 'name') else "")
                if trigger_type:
                    span.set_attribute(schema.TC_TRIGGER_TYPE, trigger_type)
        else:
            # No parent context provided - likely a root span
            span.set_attribute(schema.TC_INGRESS, True)
            trigger_type = infer_trigger_type(span.name if hasattr(span, 'name') else "")
            if trigger_type:
                span.set_attribute(schema.TC_TRIGGER_TYPE, trigger_type)

    def on_end(self, span: ReadableSpan):
        attrs = span.attributes or {}

        # Use set_attribute if available (writable Span), fallback to _attributes
        def _set(key: str, value):
            if hasattr(span, "set_attribute"):
                span.set_attribute(key, value)
            else:
                try:
                    span._attributes[key] = value
                except (TypeError, AttributeError):
                    pass

        # Agent identity — derive from OpenInference/Agno/Strands attributes
        oi_kind = attrs.get(_OI_SPAN_KIND, "")
        if oi_kind == "AGENT" and not attrs.get(schema.TC_AGENT_ID):
            agent_id = attrs.get(_AGNO_AGENT_ID) or attrs.get(_AGNO_TEAM_ID) or ""
            agent_name = attrs.get(_OI_AGENT_NAME, "")
            # Fall back: derive name from SpanName (e.g. "invoke_agent Strands Agents")
            if not agent_name:
                span_name = span.name if hasattr(span, "name") else ""
                if span_name.startswith("invoke_agent "):
                    agent_name = span_name.replace("invoke_agent ", "")
                elif span_name.endswith(".run"):
                    agent_name = span_name.replace(".run", "").replace("_", " ")
                elif span_name.endswith(".execute"):
                    agent_name = span_name.replace(".execute", "").replace("_", " ")
                elif span_name:
                    agent_name = span_name
            # Derive ID from name if no explicit ID
            if not agent_id and agent_name:
                agent_id = agent_name.lower().replace(" ", "-")
            if agent_id:
                _set(schema.TC_AGENT_ID, agent_id)
            if agent_name:
                _set(schema.TC_AGENT_NAME, agent_name)
            # Infer framework from span naming convention
            span_name_check = span.name if hasattr(span, "name") else ""
            if span_name_check.startswith("invoke_agent"):
                _set(schema.TC_AGENT_FRAMEWORK, "strands")
            elif span_name_check.startswith("openclaw."):
                _set(schema.TC_AGENT_FRAMEWORK, "openclaw")
            elif attrs.get(_AGNO_AGENT_ID) or attrs.get(_AGNO_TEAM_ID):
                _set(schema.TC_AGENT_FRAMEWORK, "agno")
            else:
                _set(schema.TC_AGENT_FRAMEWORK, "unknown")

        # Session ID — fall back to Agno's session.id
        if not attrs.get(schema.TC_SESSION_ID):
            agno_session = attrs.get(_AGNO_SESSION_ID, "")
            if agno_session:
                _set(schema.TC_SESSION_ID, agno_session)

        # Tool category and direction inference — keep result in local var since attrs is immutable snapshot
        tool_name = attrs.get(schema.TOOL_NAME, "")
        tool_desc = attrs.get(schema.TOOL_DESCRIPTION, "")
        computed_tool_cat = ""
        if tool_name:
            computed_tool_cat = infer_tool_category(tool_name, tool_desc)
            _set(schema.TC_TOOL_CATEGORY, computed_tool_cat)

            # Infer tool direction (input/output/internal)
            tool_direction = infer_tool_direction(tool_name, tool_desc)
            _set(schema.TC_TOOL_DIRECTION, tool_direction)

        # System prompt hash (16 hex chars = 64-bit, balances collision resistance + storage)
        system_prompt = attrs.get(schema.LLM_SYSTEM, "")
        if system_prompt:
            h = hashlib.sha256(system_prompt.encode()).hexdigest()[:16]
            _set(schema.TC_SYSTEM_PROMPT_HASH, h)

        # span_sequence — monotonic counter per session
        seq = _span_sequence.get(0)
        _set(schema.TC_SPAN_SEQUENCE, str(seq))
        _span_sequence.set(seq + 1)

        # memory.operation — detect from span kind + tool category
        if oi_kind == "RETRIEVER":
            _set(schema.TC_MEMORY_OPERATION, "read")
        elif computed_tool_cat == "memory_write":
            _set(schema.TC_MEMORY_OPERATION, "write")

        # input.source classification (full — Sprint 2)
        if not attrs.get(schema.TC_INPUT_SOURCE):
            caller_agent_id = attrs.get(schema.TC_CALLER_AGENT_ID, "")
            if computed_tool_cat in ("external_api", "email"):
                _set(schema.TC_INPUT_SOURCE, "external")
            elif computed_tool_cat in ("memory_read",) or oi_kind == "RETRIEVER":
                _set(schema.TC_INPUT_SOURCE, "memory")
            elif caller_agent_id:
                _set(schema.TC_INPUT_SOURCE, "agent")
            else:
                _set(schema.TC_INPUT_SOURCE, "user")

        # memory.write_provenance — trace back input source for memory writes
        mem_op = attrs.get(schema.TC_MEMORY_OPERATION, "")
        input_src = attrs.get(schema.TC_INPUT_SOURCE, "")
        if mem_op == "write" and input_src:
            _set(schema.TC_MEMORY_WRITE_PROVENANCE, input_src)

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        pass
