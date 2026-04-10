"""Compliance and data governance checks — retention, session scope, redaction."""

from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    session_cfg = config.get("session", {})
    if not isinstance(session_cfg, dict):
        session_cfg = {}

    # OC-COMP-001: Session data retention policy set
    maintenance = session_cfg.get("maintenance", {})
    if not isinstance(maintenance, dict):
        maintenance = {}
    prune_after = maintenance.get("pruneAfter")
    max_entries = maintenance.get("maxEntries")
    has_retention = bool(prune_after) or bool(max_entries)
    results.append(CheckResult(
        check_id="OC-COMP-001",
        section="Compliance",
        title="Session data retention policy is configured",
        severity=Severity.MEDIUM,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=has_retention,
        finding="Neither session.maintenance.pruneAfter nor maxEntries is set" if not has_retention else None,
        remediation="Set session.maintenance.pruneAfter (e.g. \"30d\") and/or maxEntries to enforce data retention limits.",
        config_path="session.maintenance",
        rationale="Without a retention policy, conversation data accumulates indefinitely, increasing privacy risk and storage costs.",
    ))

    # OC-COMP-002: Session scope isolates per-user data
    dm_scope = session_cfg.get("dmScope", "main")
    is_isolated = dm_scope != "main"
    results.append(CheckResult(
        check_id="OC-COMP-002",
        section="Compliance",
        title="Session scope isolates per-user conversations",
        severity=Severity.MEDIUM,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=is_isolated,
        finding=f"session.dmScope is \"{dm_scope}\" — all DM context is shared across senders" if not is_isolated else None,
        remediation="Set session.dmScope to \"per-peer\" or \"per-channel-peer\" to isolate conversations between different users.",
        config_path="session.dmScope",
        rationale="With dmScope set to \"main\", all users share the same conversation context. User A's messages and data are visible to the agent when responding to User B.",
    ))

    # OC-COMP-003: Sensitive data redaction enabled in logs
    logging_cfg = config.get("logging", {})
    if not isinstance(logging_cfg, dict):
        logging_cfg = {}
    redact = logging_cfg.get("redactSensitive", "tools")
    results.append(CheckResult(
        check_id="OC-COMP-003",
        section="Compliance",
        title="Sensitive data redaction is enabled in logs",
        severity=Severity.MEDIUM,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=redact != "off",
        finding="logging.redactSensitive is \"off\"" if redact == "off" else None,
        remediation="Set logging.redactSensitive to \"tools\" (default) to redact tokens and sensitive data from log output.",
        config_path="logging.redactSensitive",
        rationale="Disabling log redaction exposes API keys, tokens, and user data in log files, which may be captured by log aggregation systems.",
    ))

    return results
