"""Shared test fixtures for TraceCtrl integration tests."""

import pytest


@pytest.fixture
def sample_trace_id():
    """Provides a deterministic trace ID for tests."""
    return "00000000000000000000000000000001"
