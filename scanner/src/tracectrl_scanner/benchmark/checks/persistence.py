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

    # OC-PERS-003: Heartbeat is configured — autonomous periodic execution
    heartbeat_cfg = config.get("agents", {}).get("defaults", {}).get("heartbeat", {})
    heartbeat_active = isinstance(heartbeat_cfg, dict) and bool(heartbeat_cfg.get("every"))
    if heartbeat_active:
        interval = heartbeat_cfg.get("every", "")
        target = heartbeat_cfg.get("target", "")
        finding = (
            f"agents.defaults.heartbeat fires every {interval}"
            + (f" and outputs to {target}" if target else "")
            + " — agent runs autonomously on a schedule without user initiation."
        )
    else:
        finding = None
    results.append(CheckResult(
        check_id="OC-PERS-003",
        section="Persistence",
        title="Heartbeat scheduler is acknowledged and intentional",
        severity=Severity.MEDIUM,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=not heartbeat_active,
        finding=finding,
        remediation=(
            "If heartbeat is required, ensure the agent's SOUL.md restricts what it can do "
            "during unattended runs. Consider limiting tool access to read-only operations "
            "during scheduled executions. Set heartbeat.every to the minimum required interval."
        ),
        config_path="agents.defaults.heartbeat",
        rationale=(
            "A heartbeat scheduler causes the agent to run autonomously at regular intervals "
            "without user initiation. An attacker who compromises the agent's context or tools "
            "gains a persistent execution window that fires repeatedly, even when no user is present."
        ),
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
