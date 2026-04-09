from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-LAT-001: subagents.allowAgents with restrictions
    subagents = config.get("subagents", {})
    allow_agents = subagents.get("allowAgents", False)
    allow_from = subagents.get("allowFrom", [])

    if allow_agents is True:
        has_restrictions = isinstance(allow_from, list) and len(allow_from) > 0
        passed = has_restrictions
        finding = "subagents.allowAgents is true but subagents.allowFrom is empty or not set" if not passed else None
    else:
        passed = True
        finding = None

    results.append(CheckResult(
        check_id="OC-LAT-001",
        section="Lateral Movement",
        title="Sub-agent spawning has restrictions",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=passed,
        finding=finding,
        remediation="Configure subagents.allowFrom with a list of permitted agent IDs to restrict lateral movement.",
        config_path="subagents.allowFrom",
    ))

    return results
