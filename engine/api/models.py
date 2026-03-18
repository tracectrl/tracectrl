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


class AgentSummary(BaseModel):
    agent_id: str
    name: str
    framework: str
    role: str
    model: str
    tools_observed: list[str]
    system_prompt_hash: str
    run_count: int
    observation_count: int
    maturity: str
    first_seen: datetime
    last_seen: datetime


class AgentTool(BaseModel):
    tool_name: str
    tool_category: str
    call_count: int
    error_count: int
    first_seen: datetime
    last_seen: datetime


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
