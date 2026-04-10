from pathlib import Path
from typing import Any
from ..models import CheckResult, Severity, Profile, AssessmentType


def run(config: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []

    # OC-PLUG-001: Each installed plugin should have a manifest
    extensions_dir = root / "extensions"
    if not extensions_dir.exists():
        passed = True
        finding = None
    else:
        missing: list[str] = []
        for plugin_dir in extensions_dir.iterdir():
            if plugin_dir.is_dir():
                manifest = plugin_dir / "openclaw.plugin.json"
                if not manifest.exists():
                    missing.append(plugin_dir.name)
        passed = len(missing) == 0
        finding = f"Plugins missing manifest: {', '.join(missing)}" if missing else None

    results.append(CheckResult(
        check_id="OC-PLUG-001",
        section="Plugins",
        title="All plugins have a manifest file",
        severity=Severity.MEDIUM,
        profile=Profile.L2,
        assessment_type=AssessmentType.AUTOMATED,
        passed=passed,
        finding=finding,
        remediation="Add an openclaw.plugin.json manifest to each plugin directory under extensions/.",
        config_path="extensions/<plugin>/openclaw.plugin.json",
        rationale="Plugins without manifests bypass version pinning and permission declarations, making supply-chain attacks harder to detect.",
    ))

    return results
