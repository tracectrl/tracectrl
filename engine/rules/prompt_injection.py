"""vulnerableToPromptInjection (ASI01) — CVSS 7.2

Fires when: agent has tool edges with call_contexts containing external > 0
AND agent has no human_interaction tool (no guardrail).
"""

import json
from engine.rules.base import BaseRule, RuleResult, AttackStep


class PromptInjectionRule(BaseRule):

    def evaluate(self, agents, tool_edges, agent_edges):
        results = []
        for agent in agents:
            agent_id = agent["agent_id"]
            agent_tools = [e for e in tool_edges if e["agent_id"] == agent_id]

            has_external_input = False
            has_guardrail = False

            for edge in agent_tools:
                tool_category = edge["tool_category"]
                contexts = json.loads(edge["call_contexts"]) if isinstance(edge["call_contexts"], str) else edge["call_contexts"]
                if isinstance(contexts, dict) and contexts.get("external", 0) > 0:
                    has_external_input = True
                if tool_category == "human_interaction":
                    has_guardrail = True

            if has_external_input and not has_guardrail:
                results.append(RuleResult(
                    rule_name="vulnerableToPromptInjection",
                    owasp_category="ASI01",
                    agents_involved=[agent_id],
                    steps=[
                        AttackStep(agent_id, "agent", "no_input_sanitisation",
                                   f"Agent '{agent['name']}' receives external input without guardrail"),
                    ],
                    base_cvss=7.2,
                ))
        return results
