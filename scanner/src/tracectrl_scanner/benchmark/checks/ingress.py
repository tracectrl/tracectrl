from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-ING-001: Enabled channels must not have dmPolicy "open"
    channels = config.get("channels", {})
    open_channels: list[str] = []
    for name, channel_cfg in channels.items():
        if isinstance(channel_cfg, dict) and channel_cfg.get("enabled", False):
            if channel_cfg.get("dmPolicy") == "open":
                open_channels.append(name)

    results.append(CheckResult(
        check_id="OC-ING-001",
        section="Ingress",
        title="No enabled channels have open DM policy",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=len(open_channels) == 0,
        finding=f"Channels with open dmPolicy: {', '.join(open_channels)}" if open_channels else None,
        remediation='Set dmPolicy to "pairing" (requires one-time approval) or "allowlist" (explicit sender list).',
        config_path="channels.<name>.dmPolicy",
        rationale="An open DM policy lets any user message the agent, enabling prompt injection and social engineering attacks from unknown senders.",
    ))

    # OC-ING-002: Webhook auth token should be set (only if webhook is configured)
    webhook = config.get("webhook")
    if webhook is None or not isinstance(webhook, dict):
        # Webhook section not configured — check is not applicable
        passed = True
        finding = None
    else:
        auth_token = webhook.get("auth", {}).get("token", "")
        webhook_secret = webhook.get("secret", "")
        has_auth = bool(auth_token) or bool(webhook_secret)
        passed = has_auth
        finding = "Neither webhook.auth.token nor webhook.secret is set" if not has_auth else None

    results.append(CheckResult(
        check_id="OC-ING-002",
        section="Ingress",
        title="Webhook authentication is configured",
        severity=Severity.HIGH,
        profile=Profile.L2,
        assessment_type=AssessmentType.AUTOMATED,
        passed=passed,
        finding=finding,
        remediation="Configure webhook.auth.token or webhook.secret to authenticate incoming webhook requests.",
        config_path="webhook.auth.token",
        rationale="Unauthenticated webhooks let any external party trigger agent actions by sending crafted payloads to the endpoint.",
    ))

    return results
