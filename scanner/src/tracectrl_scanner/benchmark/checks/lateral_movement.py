from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-LAT-001: subagents spawning has restrictions
    # Correct path: agents.defaults.subagents (not top-level subagents)
    agents_cfg = config.get("agents", {})
    defaults = agents_cfg.get("defaults", {}) if isinstance(agents_cfg, dict) else {}
    subagents = defaults.get("subagents", {}) if isinstance(defaults, dict) else {}
    if not isinstance(subagents, dict):
        subagents = {}

    # Check if sub-agents are unrestricted
    allow_agents = subagents.get("allowAgents")
    max_depth = subagents.get("maxSpawnDepth")
    require_id = subagents.get("requireAgentId", False)

    # Fail if: allowAgents is an open list or True, with no depth limit and no requireAgentId
    if isinstance(allow_agents, list) and len(allow_agents) > 0:
        # Explicit allowlist — this is restricted
        passed = True
        finding = None
    elif allow_agents is True or allow_agents is None:
        # Unrestricted or default — check for other controls
        has_depth = isinstance(max_depth, int) and max_depth > 0
        has_require = require_id is True
        passed = has_depth or has_require
        finding = "Sub-agent spawning is unrestricted — no allowAgents list, maxSpawnDepth, or requireAgentId" if not passed else None
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
        remediation="Configure agents.defaults.subagents.allowAgents with a list of permitted agent IDs, set maxSpawnDepth, or enable requireAgentId.",
        config_path="agents.defaults.subagents",
        rationale="Unrestricted sub-agent spawning lets a compromised agent create new agents with elevated privileges, enabling lateral movement across the system.",
    ))

    return results
