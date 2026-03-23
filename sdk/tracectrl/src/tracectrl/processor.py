"""TraceCtrlSpanProcessor — enriches spans with security attributes."""

import hashlib
from contextvars import ContextVar
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from tracectrl import schema
from tracectrl.inference import infer_tool_category
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
            elif attrs.get(_AGNO_AGENT_ID) or attrs.get(_AGNO_TEAM_ID):
                _set(schema.TC_AGENT_FRAMEWORK, "agno")
            else:
                _set(schema.TC_AGENT_FRAMEWORK, "unknown")

        # Session ID — fall back to Agno's session.id
        if not attrs.get(schema.TC_SESSION_ID):
            agno_session = attrs.get(_AGNO_SESSION_ID, "")
            if agno_session:
                _set(schema.TC_SESSION_ID, agno_session)

        # Tool category inference
        tool_name = attrs.get(schema.TOOL_NAME, "")
        tool_desc = attrs.get(schema.TOOL_DESCRIPTION, "")
        if tool_name:
            _set(schema.TC_TOOL_CATEGORY, infer_tool_category(tool_name, tool_desc))

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
        elif tool_name and infer_tool_category(tool_name, tool_desc) == "memory_write":
            _set(schema.TC_MEMORY_OPERATION, "write")

        # input.source classification (full — Sprint 2)
        if not attrs.get(schema.TC_INPUT_SOURCE):
            caller_agent_id = attrs.get(schema.TC_CALLER_AGENT_ID, "")
            tool_cat = attrs.get(schema.TC_TOOL_CATEGORY, "")
            if tool_cat in ("external_api", "email"):
                _set(schema.TC_INPUT_SOURCE, "external")
            elif tool_cat in ("memory_read",) or oi_kind == "RETRIEVER":
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
