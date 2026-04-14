"""Trace context propagation helpers for cross-process spans."""

import functools
from opentelemetry import context, trace
from opentelemetry.propagate import inject, extract
from tracectrl import schema


def inject_trace_headers(headers: dict | None = None) -> dict:
    """Inject W3C traceparent into a headers dict for cross-process propagation."""
    headers = headers or {}
    inject(headers)
    return headers


def extract_trace_headers(headers: dict) -> context.Context:
    """Extract trace context from incoming headers."""
    return extract(headers)


def ingress(trigger_type: str | None = None):
    """Decorator to mark a function as an ingress point.

    Automatically creates a span and marks it with ingress metadata.

    Args:
        trigger_type: Optional trigger type ("email", "upload", "webhook", "manual", etc.)
                     If not provided, will be inferred from function name.

    Example:
        @tracectrl.ingress(trigger_type="email")
        def process_email(email):
            ...

        @tracectrl.ingress  # Auto-infers type from function name
        def handle_upload(file):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = f"{func.__module__}.{func.__name__}" if hasattr(func, '__module__') else func.__name__

            with tracer.start_as_current_span(span_name) as span:
                # Mark as ingress
                span.set_attribute(schema.TC_INGRESS, True)

                # Set trigger type (explicit or inferred)
                if trigger_type:
                    span.set_attribute(schema.TC_TRIGGER_TYPE, trigger_type)
                else:
                    # Try to infer from function name
                    from tracectrl.inference import infer_trigger_type
                    inferred_type = infer_trigger_type(func.__name__)
                    if inferred_type:
                        span.set_attribute(schema.TC_TRIGGER_TYPE, inferred_type)

                return func(*args, **kwargs)

        return wrapper

    # Support both @ingress and @ingress()
    if callable(trigger_type):
        func = trigger_type
        trigger_type = None
        return decorator(func)

    return decorator
