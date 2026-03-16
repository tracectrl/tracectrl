"""Trace context propagation helpers for cross-process spans."""

from opentelemetry import context
from opentelemetry.propagate import inject, extract


def inject_trace_headers(headers: dict | None = None) -> dict:
    """Inject W3C traceparent into a headers dict for cross-process propagation."""
    headers = headers or {}
    inject(headers)
    return headers


def extract_trace_headers(headers: dict) -> context.Context:
    """Extract trace context from incoming headers."""
    return extract(headers)
