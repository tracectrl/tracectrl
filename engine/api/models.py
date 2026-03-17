"""Pydantic response models for API endpoints."""

from pydantic import BaseModel
from datetime import datetime


class SessionSummary(BaseModel):
    trace_id: str
    start_time: datetime
    end_time: datetime
    total_duration_ns: int
    span_count: int
    root_span_name: str
    root_span_id: str
    agent_name: str
    has_error: bool


class SpanDetail(BaseModel):
    span_id: str
    parent_span_id: str
    span_name: str
    span_kind: str
    service_name: str
    start_ns: int
    duration_ns: int
    status_code: str
    status_message: str
    attributes: dict[str, str]
    resource_attributes: dict[str, str]
