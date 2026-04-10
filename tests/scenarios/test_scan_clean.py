"""Test that a clean OpenClaw config produces no CRITICAL or HIGH findings."""
import pyjson5
from pathlib import Path
from tracectrl_scanner.benchmark.runner import run_all

FIXTURES = Path(__file__).parent.parent / "fixtures" / "openclaw_configs"

def test_clean_config_no_critical():
    config = pyjson5.loads((FIXTURES / "clean.json").read_text())
    results = run_all(config, FIXTURES)
    critical = [r for r in results if r.severity.value == "CRITICAL" and not r.passed]
    assert len(critical) == 0, f"Unexpected CRITICAL findings: {[r.check_id for r in critical]}"

def test_clean_config_no_high():
    config = pyjson5.loads((FIXTURES / "clean.json").read_text())
    results = run_all(config, FIXTURES)
    high = [r for r in results if r.severity.value == "HIGH" and not r.passed]
    assert len(high) == 0, f"Unexpected HIGH findings: {[r.check_id for r in high]}"

def test_clean_config_all_checks_run():
    """All check modules should produce at least one result."""
    config = pyjson5.loads((FIXTURES / "clean.json").read_text())
    results = run_all(config, FIXTURES)
    # Every check module should contribute at least 1 result
    sections = {r.section for r in results}
    assert len(sections) >= 10, f"Expected checks from at least 10 sections, got {len(sections)}: {sections}"
    # Total should be at least 20 (allows adding checks without breaking)
    assert len(results) >= 20, f"Expected at least 20 checks, got {len(results)}"
