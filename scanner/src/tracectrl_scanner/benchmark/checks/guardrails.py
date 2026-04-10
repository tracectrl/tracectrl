from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-GUARD-001: SOUL.md must exist for each agent
    agents_dir = root / "agents"
    if not agents_dir.exists():
        # No agents directory — nothing to check, pass
        passed = True
        finding = None
    else:
        missing: list[str] = []
        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir():
                soul_path = agent_dir / "agent" / "SOUL.md"
                if not soul_path.exists():
                    missing.append(agent_dir.name)
        passed = len(missing) == 0
        finding = f"Agents missing SOUL.md: {', '.join(missing)}" if missing else None

    results.append(CheckResult(
        check_id="OC-GUARD-001",
        section="Guardrails",
        title="SOUL.md exists for each agent",
        severity=Severity.MEDIUM,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=passed,
        finding=finding,
        remediation="Create a SOUL.md file at agents/<agent_id>/agent/SOUL.md for each agent to define behavioral guardrails.",
        config_path="agents/<agent_id>/agent/SOUL.md",
        rationale="Without a SOUL.md, the agent has no explicit behavioral boundaries, making it susceptible to prompt injection that overrides its purpose.",
    ))

    # OC-GUARD-002: Content filter should be enabled
    agents_filter = config.get("agents", {}).get("defaults", {}).get("contentFilter", {}).get("enabled", False)
    tools_filter = config.get("tools", {}).get("contentFilter", {}).get("enabled", False)
    filter_enabled = agents_filter is True or tools_filter is True
    results.append(CheckResult(
        check_id="OC-GUARD-002",
        section="Guardrails",
        title="Content filter is enabled",
        severity=Severity.MEDIUM,
        profile=Profile.L2,
        assessment_type=AssessmentType.AUTOMATED,
        passed=filter_enabled,
        finding="Content filter is not enabled in agents.defaults.contentFilter or tools.contentFilter" if not filter_enabled else None,
        remediation="Enable content filtering by setting agents.defaults.contentFilter.enabled or tools.contentFilter.enabled to true.",
        config_path="agents.defaults.contentFilter.enabled",
        rationale="Without content filtering, the agent can generate or relay harmful, toxic, or policy-violating content to end users.",
    ))

    return results
