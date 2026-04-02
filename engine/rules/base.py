"""Base classes for TAGAAI attack graph rules."""

from dataclasses import dataclass


@dataclass
class AttackStep:
    node_id: str
    node_type: str  # "agent" | "tool"
    vulnerability: str
    description: str


@dataclass
class RuleResult:
    rule_name: str
    rule_id: str
    owasp_category: str
    title: str
    description: str
    agents_involved: list[str]
    steps: list[AttackStep]
    base_cvss: float
    path_nodes: list[str] = field(default_factory=list)
    path_edges: list[str] = field(default_factory=list)


class BaseRule:
    """Interface for TAGAAI rules."""

    def evaluate(self, agents: list[dict], tool_edges: list[dict],
                 agent_edges: list[dict], **kwargs) -> list[RuleResult]:
        raise NotImplementedError
