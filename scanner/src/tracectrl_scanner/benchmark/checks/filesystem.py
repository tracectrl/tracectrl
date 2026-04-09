import os
from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-FS-001: openclaw.json should not be world-readable
    config_file = root / "openclaw.json"
    if config_file.exists():
        mode = os.stat(config_file).st_mode
        world_readable = bool(mode & 0o004)
        passed = not world_readable
        finding = f"openclaw.json has mode {oct(mode)} — world-readable bit is set" if world_readable else None
    else:
        passed = True
        finding = None

    results.append(CheckResult(
        check_id="OC-FS-001",
        section="Filesystem",
        title="openclaw.json is not world-readable",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=passed,
        finding=finding,
        remediation="Restrict file permissions: chmod 600 openclaw.json",
        config_path="openclaw.json",
    ))

    # OC-FS-002: Credentials directory permissions
    creds_dir = root / "credentials"
    if creds_dir.exists() and creds_dir.is_dir():
        mode = os.stat(creds_dir).st_mode
        world_readable = bool(mode & 0o004)
        passed = not world_readable
        finding = f"credentials/ directory has mode {oct(mode)} — world-readable bit is set" if world_readable else None
    else:
        passed = True
        finding = None

    results.append(CheckResult(
        check_id="OC-FS-002",
        section="Filesystem",
        title="Credentials directory has restrictive permissions",
        severity=Severity.HIGH,
        profile=Profile.L1,
        assessment_type=AssessmentType.AUTOMATED,
        passed=passed,
        finding=finding,
        remediation="Restrict directory permissions: chmod 700 credentials/",
        config_path="credentials/",
    ))

    return results
