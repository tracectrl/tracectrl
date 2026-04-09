"""Compound risk scorer.

Combines individual check results with the topology graph to surface
high-severity compound risks that only emerge when multiple weaknesses
coexist in the same deployment.
"""

from __future__ import annotations

from typing import Any

from ..benchmark.models import CheckResult
from .models import NodeType, TopologyGraph


# Channel names that represent internet-facing ingress surfaces.
_INTERNET_CHANNELS = {"whatsapp", "telegram", "discord", "slack", "web", "api"}


def _failed_check_ids(results: list[CheckResult]) -> set[str]:
    """Return the set of check IDs that did *not* pass."""
    return {r.check_id for r in results if not r.passed}


def _has_internet_channel(graph: TopologyGraph) -> bool:
    """True if the topology contains at least one internet-facing ingress."""
    for node in graph.nodes:
        if node.type == NodeType.INGRESS:
            ch = node.properties.get("channel", "")
            if ch in _INTERNET_CHANNELS:
                return True
    return False


def _has_tool(graph: TopologyGraph, tool_name: str) -> bool:
    """True if the topology contains a tool node with the given name."""
    return any(
        n.type == NodeType.TOOL and n.label == tool_name
        for n in graph.nodes
    )


def _has_subagent_surface(graph: TopologyGraph) -> bool:
    """True if a subagent surface node exists in the graph."""
    return any(n.type == NodeType.SUBAGENT_SURFACE for n in graph.nodes)


# ----------------------------------------------------------------------- #
# Compound rules
# ----------------------------------------------------------------------- #

def _check_compound_001(
    failed: set[str], graph: TopologyGraph,
) -> dict[str, Any] | None:
    """COMPOUND-001 — Prompt Injection Highway.

    Internet channel + web_fetch tool + no SOUL.md guardrail (OC-GUARD-001).
    """
    if (
        _has_internet_channel(graph)
        and _has_tool(graph, "web_fetch")
        and "OC-GUARD-001" in failed
    ):
        return {
            "id": "COMPOUND-001",
            "title": "Prompt Injection Highway",
            "severity": "HIGH",
            "description": (
                "An internet-facing channel feeds untrusted user input to an "
                "agent that can fetch arbitrary web content, while no SOUL.md "
                "system prompt guardrail is in place. This creates a direct "
                "path for prompt-injection payloads to reach the LLM."
            ),
            "contributing_checks": ["OC-GUARD-001"],
        }
    return None


def _check_compound_002(
    failed: set[str], graph: TopologyGraph,
) -> dict[str, Any] | None:
    """COMPOUND-002 — Remote Code Execution.

    Unrestricted bash tool (OC-TOOL-001) + network bound to 0.0.0.0
    (OC-NET-001).
    """
    if "OC-TOOL-001" in failed and "OC-NET-001" in failed:
        return {
            "id": "COMPOUND-002",
            "title": "Remote Code Execution",
            "severity": "CRITICAL",
            "description": (
                "The agent has unrestricted shell access via the bash tool "
                "and the service is bound to all network interfaces "
                "(0.0.0.0). A remote attacker reaching the service can "
                "achieve full code execution on the host."
            ),
            "contributing_checks": ["OC-TOOL-001", "OC-NET-001"],
        }
    return None


def _check_compound_003(
    failed: set[str], graph: TopologyGraph,
) -> dict[str, Any] | None:
    """COMPOUND-003 — Unconstrained Lateral Movement.

    Subagent surface exists + OC-LAT-001 failed (lateral-movement controls
    absent).
    """
    if _has_subagent_surface(graph) and "OC-LAT-001" in failed:
        return {
            "id": "COMPOUND-003",
            "title": "Unconstrained Lateral Movement",
            "severity": "HIGH",
            "description": (
                "Agents are permitted to spawn sub-agents without lateral-"
                "movement restrictions. A compromised agent can propagate "
                "to other agents and escalate its privileges across the "
                "deployment."
            ),
            "contributing_checks": ["OC-LAT-001"],
        }
    return None


def _check_compound_004(
    failed: set[str], graph: TopologyGraph,
) -> dict[str, Any] | None:
    """COMPOUND-004 — Credential Exposure.

    Plaintext credentials detected (OC-CRED-001) + internet channel exists.
    """
    if "OC-CRED-001" in failed and _has_internet_channel(graph):
        return {
            "id": "COMPOUND-004",
            "title": "Credential Exposure",
            "severity": "HIGH",
            "description": (
                "Plaintext credentials are present in the configuration and "
                "the deployment is exposed to the internet via a public "
                "channel. An attacker exploiting any injection vector may "
                "exfiltrate these credentials."
            ),
            "contributing_checks": ["OC-CRED-001"],
        }
    return None


# Ordered list of all compound-rule checkers.
_COMPOUND_RULES = [
    _check_compound_001,
    _check_compound_002,
    _check_compound_003,
    _check_compound_004,
]


def score_compound_risks(
    check_results: list[CheckResult],
    graph: TopologyGraph,
) -> list[dict[str, Any]]:
    """Evaluate compound risk rules against check results and the topology.

    Returns a list of triggered compound-risk dicts, each containing:
    ``id``, ``title``, ``severity``, ``description``, and
    ``contributing_checks``.
    """
    failed = _failed_check_ids(check_results)
    findings: list[dict[str, Any]] = []

    for rule_fn in _COMPOUND_RULES:
        result = rule_fn(failed, graph)
        if result is not None:
            findings.append(result)

    return findings
