"""Test that critical configs trigger the correct findings."""
import pyjson5
from pathlib import Path
from tracectrl_scanner.benchmark.runner import run_all

FIXTURES = Path(__file__).parent.parent / "fixtures" / "openclaw_configs"

def test_critical_bind_fires():
    config = pyjson5.loads((FIXTURES / "critical_bind.json").read_text())
    results = run_all(config, FIXTURES)
    failed_ids = {r.check_id for r in results if not r.passed}
    assert "OC-NET-001" in failed_ids

def test_critical_bind_severity():
    config = pyjson5.loads((FIXTURES / "critical_bind.json").read_text())
    results = run_all(config, FIXTURES)
    net001 = next(r for r in results if r.check_id == "OC-NET-001")
    assert net001.severity.value == "CRITICAL"
    assert not net001.passed

def test_critical_bash_fires():
    config = pyjson5.loads((FIXTURES / "critical_bash.json").read_text())
    results = run_all(config, FIXTURES)
    failed_ids = {r.check_id for r in results if not r.passed}
    assert "OC-TOOL-001" in failed_ids

def test_plaintext_creds_fires():
    config = pyjson5.loads((FIXTURES / "high_plaintext_creds.json").read_text())
    results = run_all(config, FIXTURES)
    failed_ids = {r.check_id for r in results if not r.passed}
    assert "OC-LLM-001" in failed_ids or "OC-CRED-001" in failed_ids
