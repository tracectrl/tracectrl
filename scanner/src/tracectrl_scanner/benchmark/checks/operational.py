"""Operational health checks — model config, fallbacks, heartbeat, channels."""

from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    agents_cfg = config.get("agents", {})
    defaults = agents_cfg.get("defaults", {}) if isinstance(agents_cfg, dict) else {}

    # OC-OPS-001: Primary model configured
    model_cfg = defaults.get("model", {}) if isinstance(defaults, dict) else {}
    primary = model_cfg.get("primary") if isinstance(model_cfg, dict) else None
    results.append(CheckResult(
        check_id="OC-OPS-001",
        section="Operational",
        title="Primary model is configured",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=bool(primary),
        finding="agents.defaults.model.primary is not set" if not primary else None,
        remediation="Set agents.defaults.model.primary to a provider/model string (e.g. \"anthropic/claude-sonnet-4-20250514\").",
        config_path="agents.defaults.model.primary",
        rationale="Without a primary model, the agent may fail to start or use an unexpected default, causing runtime errors.",
    ))

    # OC-OPS-002: Fallback model configured
    fallbacks = model_cfg.get("fallbacks", []) if isinstance(model_cfg, dict) else []
    has_fallback = isinstance(fallbacks, list) and len(fallbacks) > 0
    results.append(CheckResult(
        check_id="OC-OPS-002",
        section="Operational",
        title="Fallback model is configured",
        severity=Severity.MEDIUM,
        profile=Profile.L2,
        assessment_type=AssessmentType.AUTOMATED,
        passed=has_fallback,
        finding="agents.defaults.model.fallbacks is empty or not set" if not has_fallback else None,
        remediation="Add at least one fallback model to agents.defaults.model.fallbacks for resilience.",
        config_path="agents.defaults.model.fallbacks",
        rationale="Without a fallback, a single provider outage means total agent downtime. Fallbacks enable automatic failover.",
    ))

    return results
