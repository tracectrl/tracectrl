"""Base classes for TAGAAI attack graph rules."""

from dataclasses import dataclass, field


@dataclass
class AttackStep:
    node_id: str
    node_type: str  # "agent" | "tool"
    vulnerability: str
    description: str


@dataclass
class RuleResult:
    rule_name: str
    owasp_category: str
    agents_involved: list[str]
    steps: list[AttackStep]
    base_cvss: float


class BaseRule:
    """Interface for TAGAAI rules."""

    def evaluate(self, agents: list[dict], tool_edges: list[dict],
                 agent_edges: list[dict], **kwargs) -> list[RuleResult]:
        raise NotImplementedError
