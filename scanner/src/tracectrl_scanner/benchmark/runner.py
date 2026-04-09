from pathlib import Path
from typing import Any
from .models import CheckResult
from .checks import (network, credentials, tools, ingress, guardrails,
                     filesystem, persistence, lateral_movement, plugins,
                     llm_providers, logging_checks)

ALL_CHECK_MODULES = [network, credentials, tools, ingress, guardrails,
                     filesystem, persistence, lateral_movement, plugins,
                     llm_providers, logging_checks]

def run_all(config: dict[str, Any], openclaw_root: Path) -> list[CheckResult]:
    results = []
    for module in ALL_CHECK_MODULES:
        results.extend(module.run(config, openclaw_root))
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "MANUAL": 3, "PASS": 4}
    return sorted(results, key=lambda r: (severity_order.get(r.severity.value, 4), r.check_id))
