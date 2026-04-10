from pathlib import Path
from typing import Any
import re
from ..models import CheckResult, Severity, Profile, AssessmentType

_SENSITIVE_KEY_NAMES = {"apikey", "api_key", "token", "secret", "password", "key"}
_SAFE_PREFIXES = ("http://", "https://", "~/", "/")


def _is_plaintext_key(key_name: str, value: str) -> bool:
    """Check if a string value under a sensitive key name looks like a plaintext secret."""
    if not isinstance(value, str) or not value:
        return False
    # Only flag values under sensitive key names
    if key_name.lower() not in _SENSITIVE_KEY_NAMES:
        return False
    # Env var references are OK
    if re.match(r"^\$\{.+\}$", value):
        return False
    # Safe prefixes (URLs, paths) are not secrets
    if value.startswith(_SAFE_PREFIXES):
        return False
    # Known key prefixes are always flagged
    if value.startswith("sk-") or value.startswith("key-"):
        return True
    # Non-empty value under a sensitive key name
    return True


def _scan_for_plaintext_keys(obj: Any, path: str = "") -> list[str]:
    """Recursively scan a dict for plaintext API key values."""
    findings: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            current_path = f"{path}.{k}" if path else k
            if isinstance(v, str) and _is_plaintext_key(k, v):
                findings.append(current_path)
            elif isinstance(v, (dict, list)):
                findings.extend(_scan_for_plaintext_keys(v, current_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            findings.extend(_scan_for_plaintext_keys(item, f"{path}[{i}]"))
    return findings


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-CRED-001: No plaintext API keys anywhere in config
    plaintext_paths = _scan_for_plaintext_keys(config)
    results.append(CheckResult(
        check_id="OC-CRED-001",
        section="Credentials",
        title="No plaintext API keys in configuration",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=len(plaintext_paths) == 0,
        finding=f"Plaintext keys found at: {', '.join(plaintext_paths)}" if plaintext_paths else None,
        remediation="Replace plaintext API keys with environment variable references using ${VAR_NAME} syntax.",
        config_path="<entire config>",
        rationale="Plaintext credentials in config files can be leaked via version control, file sharing, or log output.",
    ))

    # OC-CRED-002: .env file should be in .gitignore
    env_file = root / ".env"
    gitignore = root / ".gitignore"
    if not env_file.exists():
        passed = True
        finding = None
    else:
        if gitignore.exists():
            lines = [line.strip() for line in gitignore.read_text().splitlines()]
            passed = ".env" in lines or "/.env" in lines
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
        rationale="An unprotected .env file can be accidentally committed, exposing secrets to anyone with repository access.",
    ))

    return results
