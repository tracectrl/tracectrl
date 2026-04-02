"""vulnerableToExcessiveAgency (ASI02) — CVSS 8.1

Fires when: prompt injection fires (Rule 1)
AND agent has a high-risk tool (code_execution, email, file_system).
"""

from engine.rules.base import BaseRule, RuleResult, AttackStep

HIGH_RISK_CATEGORIES = {"code_execution", "email", "file_system"}


class ExcessiveAgencyRule(BaseRule):

    def evaluate(self, agents, tool_edges, agent_edges,
                 injection_results: list[RuleResult] | None = None):
        if not injection_results:
            return []

        vulnerable_agents = set()
        for r in injection_results:
            vulnerable_agents.update(r.agents_involved)

        results = []
        for agent in agents:
            agent_id = agent["agent_id"]
            if agent_id not in vulnerable_agents:
                continue

            agent_tools = [e for e in tool_edges if e["agent_id"] == agent_id]
            high_risk_tools = [e for e in agent_tools if e["tool_category"] in HIGH_RISK_CATEGORIES]

            for tool_edge in high_risk_tools:
                tool_name = tool_edge["tool_name"]
                tool_category = tool_edge["tool_category"]
                edge_id = tool_edge["edge_id"]
                results.append(RuleResult(
                    rule_name="vulnerableToExcessiveAgency",
                    rule_id="excessive_agency",
                    owasp_category="ASI02",
                    title="Excessive Agency Vulnerability",
                    description=f"Agent '{agent['name']}' is vulnerable to prompt injection and has access to high-risk tool '{tool_name}' ({tool_category}), enabling excessive agency attacks.",
                    agents_involved=[agent_id],
                    steps=[
                        AttackStep(agent_id, "agent", "prompt_injection",
                                   f"Agent '{agent['name']}' vulnerable to prompt injection"),
                        AttackStep(f"tool:{tool_name}", "tool", "high_risk_tool",
                                   f"Has {tool_category} tool '{tool_name}'"),
                    ],
                    base_cvss=8.1,
                    path_nodes=["external_input", agent_id, f"tool:{tool_name}"],
                    path_edges=[edge_id],
                ))
        return results
