import re
from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType

_SENSITIVE_KEYS = {"apiKey", "api_key", "token", "secret"}


def _is_plaintext_secret(value: str) -> bool:
    """Check if a string value is a plaintext secret (not an env var reference)."""
    if not isinstance(value, str) or not value:
        return False
    if re.match(r"^\$\{.+\}$", value):
        return False
    return True


def _scan_providers(providers: Any, path: str = "models.providers") -> list[str]:
    """Scan provider configs for plaintext sensitive fields."""
    findings: list[str] = []
    if isinstance(providers, dict):
        for key, value in providers.items():
            current_path = f"{path}.{key}"
            if key in _SENSITIVE_KEYS and isinstance(value, str) and _is_plaintext_secret(value):
                findings.append(current_path)
            elif isinstance(value, dict):
                findings.extend(_scan_providers(value, current_path))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    findings.extend(_scan_providers(item, f"{current_path}[{i}]"))
    return findings


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-LLM-001: No plaintext secrets in LLM provider configs
    providers = config.get("models", {}).get("providers", {})
    plaintext_paths = _scan_providers(providers)

    results.append(CheckResult(
        check_id="OC-LLM-001",
        section="LLM Providers",
        title="No plaintext secrets in LLM provider configuration",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=len(plaintext_paths) == 0,
        finding=f"Plaintext secrets found at: {', '.join(plaintext_paths)}" if plaintext_paths else None,
        remediation="Replace plaintext apiKey/token/secret values with ${ENV_VAR} references.",
        config_path="models.providers",
    ))

    return results
