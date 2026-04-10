from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def _get_tools_allow(config: dict[str, Any]) -> list[str]:
    """Collect tools.allow from both agents.defaults and top-level tools."""
    allow: list[str] = []
    agents_allow = config.get("agents", {}).get("defaults", {}).get("tools", {}).get("allow", [])
    if isinstance(agents_allow, list):
        allow.extend(agents_allow)
    top_allow = config.get("tools", {}).get("allow", [])
    if isinstance(top_allow, list):
        allow.extend(top_allow)
    return allow


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    tools_allow = _get_tools_allow(config)

    # OC-TOOL-001: bash/shell/exec must not be in tools.allow
    dangerous_tools = ("bash", "shell", "exec")
    found_dangerous = [t for t in tools_allow if t in dangerous_tools]
    has_dangerous = len(found_dangerous) > 0
    results.append(CheckResult(
        check_id="OC-TOOL-001",
        section="Tools",
        title="Shell/bash/exec tool is not permitted",
        severity=Severity.CRITICAL,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=not has_dangerous,
        finding=f"{', '.join(found_dangerous)} listed in tools.allow" if has_dangerous else None,
        remediation="Remove \"bash\", \"shell\", and \"exec\" from tools.allow to prevent arbitrary command execution.",
        config_path="tools.allow",
        rationale="bash/shell/exec tools enable arbitrary command execution on the host. An attacker who compromises the agent's prompt can run any system command.",
    ))

    # OC-TOOL-002: wildcard must not be in tools.allow
    has_wildcard = "*" in tools_allow
    results.append(CheckResult(
        check_id="OC-TOOL-002",
        section="Tools",
        title="Wildcard tool permission is not used",
        severity=Severity.CRITICAL,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=not has_wildcard,
        finding="\"*\" wildcard found in tools.allow — all tools are permitted" if has_wildcard else None,
        remediation="Replace \"*\" in tools.allow with an explicit list of permitted tools.",
        config_path="tools.allow",
        rationale="A wildcard grant permits every tool, including dangerous ones added later. Explicit allowlists enforce least-privilege.",
    ))

    # OC-TOOL-003: web_fetch requires allowedDomains
    has_web_fetch = "web_fetch" in tools_allow or "*" in tools_allow
    if has_web_fetch:
        allowed_domains = (
            config.get("tools", {}).get("web", {}).get("fetch", {}).get("allowedDomains", [])
        )
        has_domains = isinstance(allowed_domains, list) and len(allowed_domains) > 0
        passed = has_domains
        finding = "web_fetch is allowed but tools.web.fetch.allowedDomains is empty or not set" if not passed else None
    else:
        passed = True
        finding = None

    results.append(CheckResult(
        check_id="OC-TOOL-003",
        section="Tools",
        title="web_fetch has domain restrictions",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=passed,
        finding=finding,
        remediation="Configure tools.web.fetch.allowedDomains with a list of permitted domains to prevent SSRF.",
        config_path="tools.web.fetch.allowedDomains",
        rationale="Unrestricted web_fetch allows the agent to reach internal services (SSRF) or exfiltrate data to attacker-controlled URLs.",
    ))

    return results
