"""Transparent MCP tool call proxy with OTel span emission."""

import os
import logging
from opentelemetry import trace
from tracectrl import schema
from tracectrl.inference import infer_tool_category

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("tracectrl.mcp.proxy")


def trace_tool_call(tool_name: str, arguments: dict, result: str,
                    tool_description: str = "") -> None:
    with tracer.start_as_current_span(f"tool:{tool_name}") as span:
        span.set_attribute(schema.TOOL_NAME, tool_name)
        span.set_attribute(schema.TOOL_DESCRIPTION, tool_description)
        span.set_attribute(schema.TOOL_PARAMETERS, str(arguments))
        span.set_attribute(schema.TC_TOOL_CATEGORY,
                           infer_tool_category(tool_name, tool_description))
        span.set_attribute("openinference.span.kind", "TOOL")
        if len(result) <= 4096:
            span.set_attribute("output.value", result)
