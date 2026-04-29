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
    extra_trace_ids: list[str] | None = None


class AgentSummary(BaseModel):
    agent_id: str
    name: str
    framework: str
    role: str
    model: str
    tools_observed: list[str]
    tool_call_counts: dict[str, int] = {}  # tool_name -> total invocations
    total_tool_calls: int = 0
    system_prompt: str = ""
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


class AttackPathStep(BaseModel):
    node_id: str
    node_type: str
    vulnerability: str
    description: str


class AttackPath(BaseModel):
    path_id: str
    rule_name: str
    owasp_tag: str
    agents_involved: list[str]
    path_steps: list[AttackPathStep]
    risk_score: float
    severity: str
    detected_at: datetime


class AgentRisk(BaseModel):
    agent_id: str
    risk_score: float
    severity: str
    path_count: int
    top_rule: str
    computed_at: datetime


class RiskSummary(BaseModel):
    risk_score: float
    severity: str
    critical_paths: int
    agents_at_risk: int
    learning_agents: int
    computed_at: datetime


class Violation(BaseModel):
    violation_id: str
    trace_id: str
    span_id: str
    eval_span_id: str
    agent_id: str
    guardrail_name: str
    judge_model: str
    decision: str   # one of pass/fail/error
    reason: str
    evidence: str
    severity: str   # one of critical/high/medium/low
    observed_at: datetime
