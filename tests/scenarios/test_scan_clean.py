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

def test_clean_config_21_checks():
    config = pyjson5.loads((FIXTURES / "clean.json").read_text())
    results = run_all(config, FIXTURES)
    assert len(results) == 21, f"Expected 21 checks, got {len(results)}"
