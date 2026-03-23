"""Risk scoring formula for attack paths."""

from engine.rules.base import RuleResult

TOOL_CATEGORY_WEIGHTS = {
    "code_execution": 1.0, "email": 0.8, "external_api": 0.7,
    "file_system": 0.7, "memory_write": 0.6, "memory_read": 0.4,
    "human_interaction": 0.3, "internal_api": 0.3,
}

INPUT_SOURCE_WEIGHTS = {
    "external": 1.0, "memory": 0.7, "agent": 0.5, "user": 0.3,
}

SEVERITY_THRESHOLDS = [
    (7.0, "Critical"),
    (5.0, "High"),
    (3.0, "Medium"),
    (0.0, "Low"),
]


def compute_path_risk(rule_result: RuleResult, tool_category: str = "internal_api",
                      input_source: str = "user", hop_count: int = 1) -> float:
    hop_mult = {1: 1.0, 2: 1.3, 3: 1.6}.get(min(hop_count, 3), 2.0)
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
