"""vulnerableToDataLeakage (ASI01+ASI02) — CVSS 6.8

Fires when: prompt injection fires (Rule 1)
AND agent has an external_api or email tool (can exfiltrate data).
"""

from engine.rules.base import BaseRule, RuleResult, AttackStep

EXFIL_CATEGORIES = {"external_api", "email"}


class DataLeakageRule(BaseRule):

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
            exfil_tools = [e for e in agent_tools if e["tool_category"] in EXFIL_CATEGORIES]

            for tool_edge in exfil_tools:
                tool_name = tool_edge["tool_name"]
                tool_category = tool_edge["tool_category"]
                results.append(RuleResult(
                    rule_name="vulnerableToDataLeakage",
                    owasp_category="ASI01+ASI02",
                    agents_involved=[agent_id],
                    steps=[
                        AttackStep(agent_id, "agent", "prompt_injection",
                                   f"Agent '{agent['name']}' vulnerable to injection"),
                        AttackStep(f"tool:{tool_name}", "tool", "data_exfiltration",
                                   f"Can exfiltrate via {tool_category} tool '{tool_name}'"),
                    ],
                    base_cvss=6.8,
                ))
        return results
