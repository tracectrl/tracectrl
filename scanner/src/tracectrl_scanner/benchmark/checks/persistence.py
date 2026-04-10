from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-PERS-001: cron.enabled should be false unless explicitly needed
    cron_enabled = config.get("cron", {}).get("enabled", False)
    results.append(CheckResult(
        check_id="OC-PERS-001",
        section="Persistence",
        title="Cron scheduling is disabled",
        severity=Severity.MEDIUM,
        profile=Profile.L2,
        assessment_type=AssessmentType.AUTOMATED,
        passed=cron_enabled is not True,
        finding="cron.enabled is true — scheduled tasks are active" if cron_enabled is True else None,
        remediation="Disable cron scheduling by setting cron.enabled to false unless explicitly required.",
        config_path="cron.enabled",
        rationale="Cron-triggered agent runs execute without user initiation, expanding the window for unattended prompt injection or resource abuse.",
    ))

    # OC-PERS-002: Session maintenance should be configured (only if session section exists)
    session_cfg = config.get("session")
    if session_cfg is None or not isinstance(session_cfg, dict):
        # Session section not configured — check is not applicable
        has_maintenance = True
        finding = None
    else:
        maintenance = session_cfg.get("maintenance", {})
        prune_after = maintenance.get("pruneAfter")
        max_entries = maintenance.get("maxEntries")
        has_maintenance = bool(prune_after) or bool(max_entries)
        finding = "Neither session.maintenance.pruneAfter nor session.maintenance.maxEntries is configured" if not has_maintenance else None

    results.append(CheckResult(
        check_id="OC-PERS-002",
        section="Persistence",
        title="Session maintenance is configured",
        severity=Severity.MEDIUM,
        profile=Profile.L2,
        assessment_type=AssessmentType.AUTOMATED,
        passed=has_maintenance,
        finding=finding,
        remediation="Configure session.maintenance.pruneAfter or session.maintenance.maxEntries to limit session data growth.",
        config_path="session.maintenance",
        rationale="Unbounded session history accumulates sensitive data and increases context size, raising both privacy risk and cost.",
    ))

    return results
