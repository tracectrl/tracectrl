from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-LOG-001: Audit logging should be enabled
    logging_cfg = config.get("logging", {})
    audit_enabled = logging_cfg.get("audit", False)
    results.append(CheckResult(
        check_id="OC-LOG-001",
        section="Logging",
        title="Audit logging is enabled",
        severity=Severity.MEDIUM,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=audit_enabled is True,
        finding="logging.audit is not enabled" if audit_enabled is not True else None,
        remediation="Enable audit logging by setting logging.audit to true.",
        config_path="logging.audit",
        rationale="Without audit logs, there is no forensic trail to detect or investigate agent misuse, prompt injection, or data exfiltration.",
    ))

    # OC-LOG-002: Log level should not be "debug" in production
    log_level = logging_cfg.get("level", "info")
    is_debug = str(log_level).lower() == "debug"
    results.append(CheckResult(
        check_id="OC-LOG-002",
        section="Logging",
        title="Log level is not set to debug",
        severity=Severity.MEDIUM,
        profile=Profile.L2,
        assessment_type=AssessmentType.AUTOMATED,
        passed=not is_debug,
        finding="logging.level is set to \"debug\" — may expose sensitive data in production" if is_debug else None,
        remediation="Set logging.level to \"info\" or \"warn\" for production deployments.",
        config_path="logging.level",
        rationale="Debug-level logs often include full prompts, API keys, and user data, which can be captured by log aggregation systems.",
    ))

    return results
