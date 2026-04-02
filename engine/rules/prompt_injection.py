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
                # Find external tool for path tracking
                external_tool = None
                external_edge_id = None
                for edge in agent_tools:
                    contexts = json.loads(edge["call_contexts"]) if isinstance(edge["call_contexts"], str) else edge["call_contexts"]
                    if isinstance(contexts, dict) and contexts.get("external", 0) > 0:
                        external_tool = edge["tool_name"]
                        external_edge_id = edge["edge_id"]
                        break

                results.append(RuleResult(
                    rule_name="vulnerableToPromptInjection",
                    rule_id="prompt_injection",
                    owasp_category="ASI01",
                    title="Prompt Injection Vulnerability",
                    description=f"Agent '{agent['name']}' processes external input without human guardrails, exposing it to prompt injection attacks.",
                    agents_involved=[agent_id],
                    steps=[
                        AttackStep(agent_id, "agent", "no_input_sanitisation",
                                   f"Agent '{agent['name']}' receives external input without guardrail"),
                    ],
                    base_cvss=7.2,
                    path_nodes=["external_input", agent_id, f"tool:{external_tool}"] if external_tool else ["external_input", agent_id],
                    path_edges=[external_edge_id] if external_edge_id else [],
                ))
        return results
