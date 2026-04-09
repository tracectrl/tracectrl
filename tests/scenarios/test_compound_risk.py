"""Test compound risk scoring."""
import pyjson5
from pathlib import Path
from tracectrl_scanner.benchmark.runner import run_all
from tracectrl_scanner.topology.builder import build
from tracectrl_scanner.topology.risk import score_compound_risks

FIXTURES = Path(__file__).parent.parent / "fixtures" / "openclaw_configs"

def test_compound_003_fires():
    """Subagents enabled + no restriction = COMPOUND-003."""
    config = pyjson5.loads((FIXTURES / "compound_risk.json").read_text())
    results = run_all(config, FIXTURES)
    graph = build(config, FIXTURES, ["main"])
    compound = score_compound_risks(results, graph)
    ids = {c["id"] for c in compound}
    assert "COMPOUND-003" in ids

def test_compound_002_fires():
    """Bash + bind 0.0.0.0 = COMPOUND-002 (RCE)."""
    config = pyjson5.loads((FIXTURES / "critical_bind.json").read_text())
    # Add bash to create compound risk
    config.setdefault("agents", {}).setdefault("defaults", {}).setdefault("tools", {})["allow"] = ["bash"]
    results = run_all(config, FIXTURES)
    graph = build(config, FIXTURES, [])
    compound = score_compound_risks(results, graph)
    ids = {c["id"] for c in compound}
    assert "COMPOUND-002" in ids

def test_clean_no_compound():
    """Clean config should produce no compound signals."""
    config = pyjson5.loads((FIXTURES / "clean.json").read_text())
    results = run_all(config, FIXTURES)
    graph = build(config, FIXTURES, ["main"])
    compound = score_compound_risks(results, graph)
    assert len(compound) == 0
