"""Advanced security checks — dangerously* flags, sandbox, exec, SSRF, Control UI."""

from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


# All known dangerously* flags in OpenClaw config
_DANGEROUS_FLAGS = [
    ("browser.ssrfPolicy.dangerouslyAllowPrivateNetwork", True),
    ("gateway.controlUi.dangerouslyDisableDeviceAuth", False),
    ("gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback", False),
    ("gateway.allowRealIpFallback", False),
    ("channels.telegram.network.dangerouslyAllowPrivateNetwork", False),
    ("channels.discord.dangerouslyAllowNameMatching", False),
    ("channels.slack.dangerouslyAllowNameMatching", False),
    ("channels.googlechat.dangerouslyAllowNameMatching", False),
    ("channels.teams.dangerouslyAllowNameMatching", False),
    ("agents.defaults.sandbox.docker.dangerouslyAllowHostNetwork", False),
    ("agents.defaults.sandbox.docker.dangerouslyRelaxSeccomp", False),
    ("agents.defaults.sandbox.docker.dangerouslyRelaxAppArmor", False),
    ("agents.defaults.sandbox.docker.dangerouslyAllowBindMounts", False),
]


def _resolve_path(config: dict, dotpath: str) -> Any:
    """Resolve a dotted config path like 'gateway.controlUi.enabled'."""
    parts = dotpath.split(".")
    obj = config
    for part in parts:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return obj


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-SEC-001: Gateway auth required when bind is non-loopback
    gateway = config.get("gateway", {})
    bind_addr = gateway.get("bind", "loopback")
    auth_cfg = gateway.get("auth", {})
    auth_mode = auth_cfg.get("mode", "none") if isinstance(auth_cfg, dict) else "none"
    is_exposed = bind_addr not in ("loopback", "127.0.0.1", "localhost")
    has_auth = auth_mode not in ("none", None, "")

    if is_exposed:
        passed = has_auth
        finding = f"gateway.bind is \"{bind_addr}\" but auth.mode is \"{auth_mode}\"" if not passed else None
    else:
        passed = True
        finding = None

    results.append(CheckResult(
        check_id="OC-SEC-001",
        section="Security",
        title="Gateway auth enabled when network-exposed",
        severity=Severity.CRITICAL,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=passed,
        finding=finding,
        remediation="Set gateway.auth.mode to \"token\" or \"password\" when gateway.bind is not loopback.",
        config_path="gateway.auth.mode",
        rationale="A network-exposed gateway without authentication allows any device on the network to control your AI agent.",
    ))

    # OC-SEC-002: No dangerously* flags enabled
    flagged = []
    for dotpath, default_is_dangerous in _DANGEROUS_FLAGS:
        value = _resolve_path(config, dotpath)
        if value is None:
            # Flag not set — check if the default is dangerous
            if default_is_dangerous:
                flagged.append(f"{dotpath} (default: dangerous)")
        elif value is True:
            flagged.append(dotpath)

    results.append(CheckResult(
        check_id="OC-SEC-002",
        section="Security",
        title="No dangerous override flags enabled",
        severity=Severity.CRITICAL,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=len(flagged) == 0,
        finding=f"Dangerous flags active: {', '.join(flagged)}" if flagged else None,
        remediation="Disable all dangerously* flags unless absolutely required. Each flag explicitly weakens a security boundary.",
        config_path="<multiple>",
        rationale="OpenClaw's dangerously* flags are explicit security opt-outs. Each one removes a protection layer — private network access, device auth, container isolation, etc.",
    ))

    # OC-SEC-003: tools.exec.security not "full"
    tools_cfg = config.get("tools", {})
    exec_cfg = tools_cfg.get("exec", {}) if isinstance(tools_cfg, dict) else {}
    exec_security = exec_cfg.get("security", "deny") if isinstance(exec_cfg, dict) else "deny"
    results.append(CheckResult(
        check_id="OC-SEC-003",
        section="Security",
        title="Exec tool security is not set to full",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=exec_security != "full",
        finding=f"tools.exec.security is \"{exec_security}\"" if exec_security == "full" else None,
        remediation="Set tools.exec.security to \"deny\" or remove it to prevent unrestricted command execution.",
        config_path="tools.exec.security",
        rationale="Setting exec security to \"full\" allows the agent to execute any shell command on the host without restriction.",
    ))

    # OC-SEC-004: Sandbox mode enabled
    agents_cfg = config.get("agents", {})
    defaults = agents_cfg.get("defaults", {}) if isinstance(agents_cfg, dict) else {}
    sandbox_cfg = defaults.get("sandbox", {}) if isinstance(defaults, dict) else {}
    sandbox_mode = sandbox_cfg.get("mode", "off") if isinstance(sandbox_cfg, dict) else "off"
    results.append(CheckResult(
        check_id="OC-SEC-004",
        section="Security",
        title="Agent sandbox is enabled",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=sandbox_mode != "off",
        finding=f"sandbox.mode is \"{sandbox_mode}\"" if sandbox_mode == "off" else None,
        remediation="Set agents.defaults.sandbox.mode to \"non-main\" or \"all\" to isolate agent tool execution.",
        config_path="agents.defaults.sandbox.mode",
        rationale="Without sandboxing, agent tools (file ops, code execution) run directly on the host with the gateway's full permissions.",
    ))

    # OC-SEC-005: Browser SSRF policy restricts private networks
    browser_cfg = config.get("browser", {})
    ssrf_cfg = browser_cfg.get("ssrfPolicy", {}) if isinstance(browser_cfg, dict) else {}
    allow_private = ssrf_cfg.get("dangerouslyAllowPrivateNetwork", True) if isinstance(ssrf_cfg, dict) else True
    results.append(CheckResult(
        check_id="OC-SEC-005",
        section="Security",
        title="Browser SSRF policy blocks private networks",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=allow_private is not True,
        finding="browser.ssrfPolicy.dangerouslyAllowPrivateNetwork is true (default)" if allow_private is True else None,
        remediation="Set browser.ssrfPolicy.dangerouslyAllowPrivateNetwork to false to prevent the agent's browser from reaching internal services.",
        config_path="browser.ssrfPolicy.dangerouslyAllowPrivateNetwork",
        rationale="When enabled (the default), the agent's browser can reach private IP ranges (10.x, 172.16.x, 192.168.x), enabling SSRF attacks against internal infrastructure.",
    ))

    return results
