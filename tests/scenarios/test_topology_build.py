"""Test that the topology builder produces correct graphs."""
import pyjson5
from pathlib import Path
from tracectrl_scanner.topology.builder import build
from tracectrl_scanner.topology.models import NodeType

FIXTURES = Path(__file__).parent.parent / "fixtures" / "openclaw_configs"

def test_clean_config_has_nodes():
    config = pyjson5.loads((FIXTURES / "clean.json").read_text())
    graph = build(config, FIXTURES, ["main"])
    assert len(graph.nodes) > 0

def test_clean_config_has_agent_node():
    config = pyjson5.loads((FIXTURES / "clean.json").read_text())
    graph = build(config, FIXTURES, ["main"])
    agent_nodes = [n for n in graph.nodes if n.type == NodeType.AGENT]
    assert len(agent_nodes) >= 1

def test_clean_config_has_ingress():
    config = pyjson5.loads((FIXTURES / "clean.json").read_text())
    graph = build(config, FIXTURES, ["main"])
    ingress = [n for n in graph.nodes if n.type == NodeType.INGRESS]
    assert len(ingress) >= 1  # telegram is enabled

def test_clean_config_has_edges():
    config = pyjson5.loads((FIXTURES / "clean.json").read_text())
    graph = build(config, FIXTURES, ["main"])
    assert len(graph.edges) > 0

def test_compound_config_has_subagent_surface():
    config = pyjson5.loads((FIXTURES / "compound_risk.json").read_text())
    graph = build(config, FIXTURES, ["main"])
    sub = [n for n in graph.nodes if n.type == NodeType.SUBAGENT_SURFACE]
    assert len(sub) >= 1
