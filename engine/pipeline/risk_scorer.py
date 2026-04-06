"""Risk scoring formula for attack paths."""

from engine.rules.base import RuleResult

TOOL_CATEGORY_WEIGHTS = {
    "code_execution": 1.0, "email": 0.8, "external_api": 0.7,
    "file_system": 0.7, "memory_write": 0.6, "memory_read": 0.4,
    "human_interaction": 0.3, "internal_api": 0.3,
}

INPUT_SOURCE_WEIGHTS = {
    # External untrusted sources (webhooks, file uploads, external APIs)
    "external": 1.0,
    # User input (authenticated users can still be malicious: prompt injection, insider threats)
    "user": 0.8,
    # Memory/vector stores (could contain poisoned data from earlier)
    "memory": 0.7,
    # Inter-agent communication (internal data flow, lower risk)
    "agent": 0.5,
}

SEVERITY_THRESHOLDS = [
    (7.0, "Critical"),
    (5.0, "High"),
    (3.0, "Medium"),
    (0.0, "Low"),
]


def compute_path_risk(rule_result: RuleResult, tool_category: str = "internal_api",
                      input_source: str = "user", hop_count: int = 1) -> float:
    """Calculate risk score for an attack path.

    Args:
        rule_result: The attack path result with base CVSS score
        tool_category: Category of the endpoint tool (code_execution, email, etc.)
        input_source: Source of untrusted input (external, user, memory, agent)
        hop_count: Number of agents in the attack path

    Returns:
        Risk score (float)

    Note: Longer attack chains have LOWER multipliers because they're harder to exploit
    (more failure points, more complexity, lower likelihood of success).
    """
    # INVERTED hop multiplier: longer chains = harder to exploit = lower risk
    hop_mult = {1: 1.0, 2: 0.95, 3: 0.85, 4: 0.75}.get(min(hop_count, 4), 0.7)

    return (
        rule_result.base_cvss
        * TOOL_CATEGORY_WEIGHTS.get(tool_category, 0.3)
        * INPUT_SOURCE_WEIGHTS.get(input_source, 0.3)
        * hop_mult
    )


def severity_for_score(score: float) -> str:
    for threshold, label in SEVERITY_THRESHOLDS:
        if score >= threshold:
            return label
    return "Low"
