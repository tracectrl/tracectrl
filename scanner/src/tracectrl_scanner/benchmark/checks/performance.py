"""Performance and cost checks — sub-agent limits, timeouts, concurrency."""

from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    agents_cfg = config.get("agents", {})
    defaults = agents_cfg.get("defaults", {}) if isinstance(agents_cfg, dict) else {}
    subagents = defaults.get("subagents", {}) if isinstance(defaults, dict) else {}
    if not isinstance(subagents, dict):
        subagents = {}

    # OC-PERF-001: Sub-agent timeout configured (default 0 = no timeout)
    timeout = subagents.get("runTimeoutSeconds", 0)
    results.append(CheckResult(
        check_id="OC-PERF-001",
        section="Performance",
        title="Sub-agent run timeout is configured",
        severity=Severity.MEDIUM,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=isinstance(timeout, (int, float)) and timeout > 0,
        finding=f"subagents.runTimeoutSeconds is {timeout} (no timeout)" if not (isinstance(timeout, (int, float)) and timeout > 0) else None,
        remediation="Set agents.defaults.subagents.runTimeoutSeconds to a reasonable limit (e.g. 300) to prevent runaway sub-agents.",
        config_path="agents.defaults.subagents.runTimeoutSeconds",
        rationale="Without a timeout, a runaway sub-agent can consume tokens and compute indefinitely, leading to unexpected costs.",
    ))

    # OC-PERF-002: Sub-agent concurrency bounded
    max_concurrent = subagents.get("maxConcurrent")
    results.append(CheckResult(
        check_id="OC-PERF-002",
        section="Performance",
        title="Sub-agent concurrency is bounded",
        severity=Severity.MEDIUM,
        profile=Profile.L2,
        assessment_type=AssessmentType.AUTOMATED,
        passed=isinstance(max_concurrent, int) and max_concurrent > 0,
        finding="subagents.maxConcurrent is not configured" if not (isinstance(max_concurrent, int) and max_concurrent > 0) else None,
        remediation="Set agents.defaults.subagents.maxConcurrent to limit parallel sub-agent runs (default: 8).",
        config_path="agents.defaults.subagents.maxConcurrent",
        rationale="Unbounded sub-agent concurrency can exhaust API rate limits and compute resources during burst activity.",
    ))

    return results
