from pathlib import Path
from typing import Any
import re
from ..models import CheckResult, Severity, Profile, AssessmentType


def _is_plaintext_key(value: str) -> bool:
    """Check if a string value looks like a plaintext API key."""
    if not isinstance(value, str) or not value:
        return False
    # Env var references are OK
    if re.match(r"^\$\{.+\}$", value):
        return False
    if value.startswith("sk-") or value.startswith("key-"):
        return True
    if len(value) > 20:
        return True
    return False


def _scan_for_plaintext_keys(obj: Any, path: str = "") -> list[str]:
    """Recursively scan a dict for plaintext API key values."""
    findings: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            current_path = f"{path}.{k}" if path else k
            if isinstance(v, str) and _is_plaintext_key(v):
                findings.append(current_path)
            elif isinstance(v, (dict, list)):
                findings.extend(_scan_for_plaintext_keys(v, current_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            findings.extend(_scan_for_plaintext_keys(item, f"{path}[{i}]"))
    return findings


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-CRED-001: No plaintext API keys in config
    providers = config.get("models", {}).get("providers", {})
    plaintext_paths = _scan_for_plaintext_keys(providers, "models.providers")
    results.append(CheckResult(
        check_id="OC-CRED-001",
        section="Credentials",
        title="No plaintext API keys in model provider config",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=len(plaintext_paths) == 0,
        finding=f"Plaintext keys found at: {', '.join(plaintext_paths)}" if plaintext_paths else None,
        remediation="Replace plaintext API keys with environment variable references using ${VAR_NAME} syntax.",
        config_path="models.providers",
    ))

    # OC-CRED-002: .env file should be in .gitignore
    env_file = root / ".env"
    gitignore = root / ".gitignore"
    if not env_file.exists():
        passed = True
        finding = None
    else:
        if gitignore.exists():
            gitignore_content = gitignore.read_text()
            passed = ".env" in gitignore_content.splitlines() or ".env" in gitignore_content
            finding = ".env file exists but is not listed in .gitignore" if not passed else None
        else:
            passed = False
            finding = ".env file exists but no .gitignore file found"

    results.append(CheckResult(
        check_id="OC-CRED-002",
        section="Credentials",
        title=".env file is protected by .gitignore",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=passed,
        finding=finding,
        remediation="Add .env to your .gitignore file to prevent accidental commits of secrets.",
        config_path=".env",
    ))

    return results
