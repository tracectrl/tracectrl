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
    provider: str = "judge_llm"  # judge_llm | protector_plus


class GuardrailInvocation(BaseModel):
    """One `tracectrl.guardrail.evaluation` span — pass, fail, or error.

    Surfaces in the Guardrail detail drawer's Recent Invocations panel.
    `response_json` is populated only for Protector Plus spans (legacy
    judge_llm spans don't carry a structured response payload).
    """
    trace_id: str
    span_id: str
    observed_at: datetime
    decision: str       # pass | fail | error
    timing: str         # pre_input | post_output
    reason: str
    evidence: str
    severity: str
    provider: str       # judge_llm | protector_plus
    judge_model: str
    response_json: str = ""


class GuardrailRegistration(BaseModel):
    agent_id: str
    guardrail_name: str
    severity: str        # low|medium|high|critical
    mode: str            # monitoring|blocking
    timing: str          # post_output|pre_input
    judge_model: str
    description: str
    judge_prompt: str = ""
    health: str          # active|error|disabled
    health_reason: str
    registered_at: datetime
    last_seen_at: datetime
    recent_activity_24h: int = 0
    provider: str = "judge_llm"  # judge_llm | protector_plus


class ProtectorConfig(BaseModel):
    """Public Protector Plus config — api_key is redacted in GET responses."""
    endpoint_url: str
    api_key: str  # redacted ('hOjm***vY2') in GET, full key in PUT body
    enabled_guardrails: list[str]
    updated_at: datetime | None = None


class ProtectorConfigUpsert(BaseModel):
    """Body for PUT /guardrails/protector-config — full api_key required."""
    endpoint_url: str
    api_key: str
    enabled_guardrails: list[str]


class ProtectorTestResult(BaseModel):
    """Response from POST /guardrails/protector-test."""
    ok: bool
    ms: int
    status_code: int | None = None
    error: str | None = None
