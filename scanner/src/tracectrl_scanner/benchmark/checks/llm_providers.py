from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-LLM-001: LLM provider configuration hygiene
    # Credential scanning is handled by OC-CRED-001; this check focuses on
    # provider-specific configuration issues (missing provider field, HTTP endpoints).
    providers = config.get("models", {}).get("providers", {})

    issues: list[str] = []
    for name, provider_cfg in providers.items():
        if not isinstance(provider_cfg, dict):
            continue
        # Check for missing provider type
        if not provider_cfg.get("provider"):
            issues.append(f"models.providers.{name}: missing 'provider' field")
        # Check for HTTP (non-TLS) endpoint
        endpoint = provider_cfg.get("endpoint", "") or provider_cfg.get("baseUrl", "")
        if isinstance(endpoint, str) and endpoint.startswith("http://"):
            issues.append(f"models.providers.{name}: endpoint uses HTTP instead of HTTPS")

    passed = len(issues) == 0
    results.append(CheckResult(
        check_id="OC-LLM-001",
        section="LLM Providers",
        title="LLM provider configuration is well-formed and secure",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=passed,
        finding="; ".join(issues) if issues else None,
        remediation=(
            "Ensure each provider has a 'provider' field and uses HTTPS endpoints. "
            "Credential scanning is handled by OC-CRED-001."
        ),
        config_path="models.providers",
        rationale="Missing provider fields cause runtime errors; HTTP endpoints transmit API keys and prompts in cleartext, enabling interception.",
    ))

    return results
