"""OTLP exporter convenience setup."""

from tracectrl.config import get_tracer_provider


def setup_exporter():
    """Ensure the tracer provider and exporter are initialized."""
    return get_tracer_provider()
