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
        rationale="Binding to 0.0.0.0 exposes the gateway to all network interfaces, allowing any device on the network to send messages to your AI agent.",
    ))

    # OC-NET-002: webhook.tls.enabled should be true (only if webhook is configured)
    webhook = config.get("webhook")
    if webhook is None or not isinstance(webhook, dict):
        # Webhook section not configured — check is not applicable
        tls_passed = True
        tls_finding = None
    else:
        tls_enabled = webhook.get("tls", {}).get("enabled", False)
        tls_passed = tls_enabled is True
        tls_finding = "webhook.tls.enabled is not true" if not tls_passed else None

    results.append(CheckResult(
        check_id="OC-NET-002",
        section="Network",
        title="Webhook TLS is enabled",
        severity=Severity.HIGH,
        profile=Profile.L2,
        assessment_type=AssessmentType.AUTOMATED,
        passed=tls_passed,
        finding=tls_finding,
        remediation="Enable TLS for webhooks by setting webhook.tls.enabled to true.",
        config_path="webhook.tls.enabled",
        rationale="Without TLS, webhook payloads including auth tokens and agent instructions are transmitted in cleartext and can be intercepted.",
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
        rationale="Without an allowed-hosts list, the gateway accepts requests for any hostname, enabling host-header injection and DNS rebinding attacks.",
    ))

    return results
