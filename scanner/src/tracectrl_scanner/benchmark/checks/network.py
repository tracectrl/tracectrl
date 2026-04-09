from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-NET-001: gateway.bind must not be "0.0.0.0"
    gateway = config.get("gateway", {})
    bind_addr = gateway.get("bind", "127.0.0.1")
    results.append(CheckResult(
        check_id="OC-NET-001",
        section="Network",
        title="Gateway bind address is not 0.0.0.0",
        severity=Severity.CRITICAL,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=bind_addr != "0.0.0.0",
        finding=f"gateway.bind is set to \"{bind_addr}\"" if bind_addr == "0.0.0.0" else None,
        remediation="Set gateway.bind to \"127.0.0.1\" or a specific internal IP address.",
        config_path="gateway.bind",
    ))

    # OC-NET-002: webhook.tls.enabled should be true
    webhook = config.get("webhook", {})
    tls_enabled = webhook.get("tls", {}).get("enabled", False)
    results.append(CheckResult(
        check_id="OC-NET-002",
        section="Network",
        title="Webhook TLS is enabled",
        severity=Severity.HIGH,
        profile=Profile.L2,
        assessment_type=AssessmentType.AUTOMATED,
        passed=tls_enabled is True,
        finding="webhook.tls.enabled is not true" if not tls_enabled else None,
        remediation="Enable TLS for webhooks by setting webhook.tls.enabled to true.",
        config_path="webhook.tls.enabled",
    ))

    # OC-NET-003: gateway.allowedHosts should be a non-empty list
    allowed_hosts = gateway.get("allowedHosts", [])
    has_hosts = isinstance(allowed_hosts, list) and len(allowed_hosts) > 0
    results.append(CheckResult(
        check_id="OC-NET-003",
        section="Network",
        title="Gateway allowed hosts list is configured",
        severity=Severity.MEDIUM,
        profile=Profile.L2,
        assessment_type=AssessmentType.AUTOMATED,
        passed=has_hosts,
        finding="gateway.allowedHosts is empty or not set" if not has_hosts else None,
        remediation="Configure gateway.allowedHosts with a list of permitted hostnames.",
        config_path="gateway.allowedHosts",
    ))

    return results
