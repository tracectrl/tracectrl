"""TraceCtrlSpanProcessor — enriches spans with security attributes."""

import hashlib
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor
from tracectrl import schema
from tracectrl.inference import infer_tool_category
from tracectrl.session import current_session_id

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

        # Agent identity — derive from OpenInference/Agno attributes
        oi_kind = attrs.get(_OI_SPAN_KIND, "")
        if oi_kind == "AGENT" and not attrs.get(schema.TC_AGENT_ID):
            agent_id = attrs.get(_AGNO_AGENT_ID) or attrs.get(_AGNO_TEAM_ID) or ""
            agent_name = attrs.get(_OI_AGENT_NAME, "")
            # Fall back: derive ID from name if agno.agent.id is missing
            if not agent_id and agent_name:
                agent_id = agent_name.lower().replace(" ", "-")
            if agent_id:
                _set(schema.TC_AGENT_ID, agent_id)
            if agent_name:
                _set(schema.TC_AGENT_NAME, agent_name)
            _set(schema.TC_AGENT_FRAMEWORK, "agno")

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

        # input.source (basic — Sprint 1)
        caller_agent_id = attrs.get(schema.TC_CALLER_AGENT_ID, "")
        if not attrs.get(schema.TC_INPUT_SOURCE):
            _set(schema.TC_INPUT_SOURCE, "agent" if caller_agent_id else "user")

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        pass
