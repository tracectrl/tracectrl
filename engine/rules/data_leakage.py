"""vulnerableToDataLeakage (ASI01+ASI02) — CVSS 6.8

Fires when: prompt injection fires (Rule 1)
AND agent has an external_api or email tool (can exfiltrate data).

Now includes multi-hop exfiltration path detection: sensitive data
flowing from one agent to another agent with exfiltration capability.
"""

import json
from engine.rules.base import BaseRule, RuleResult, AttackStep

EXFIL_CATEGORIES = {"external_api", "email"}
SENSITIVE_DATA_CATEGORIES = {"memory_read", "database", "internal_api"}
SENSITIVE_TOOL_PATTERNS = ["sanctions", "transaction", "customer", "payment", "policy"]

# Internal tools that should NOT be considered exfiltration vectors
TRUSTED_INTERNAL_TOOLS = {
    "fetch_notion_policy",
    "query_transaction_history",
    "parse_pdf",
    "read_database",
    "get_policy",
}


class DataLeakageRule(BaseRule):

    def evaluate(self, agents, tool_edges, agent_edges,
                 injection_results: list[RuleResult] | None = None):
        if not injection_results:
            return []

        vulnerable_agents = set()
        for r in injection_results:
            vulnerable_agents.update(r.agents_involved)

        results = []
        graph = self.build_bidirectional_graph(agent_edges)

        # Find agents with exfiltration capability (excluding trusted internal tools)
        filtered_tool_edges = [e for e in tool_edges if e["tool_name"] not in TRUSTED_INTERNAL_TOOLS]
        exfil_agents = self.find_agents_with_tools(agents, filtered_tool_edges, categories=EXFIL_CATEGORIES)

        # Find agents handling sensitive data
        sensitive_agents = set()
        for edge in tool_edges:
            if edge['tool_category'] in SENSITIVE_DATA_CATEGORIES:
                if any(pattern in edge['tool_name'].lower() for pattern in SENSITIVE_TOOL_PATTERNS):
                    sensitive_agents.add(edge['agent_id'])

        # Pattern 1: Direct exfiltration (vulnerable agent has exfil tool)
        # DISABLED: This creates standalone findings without showing the ingress path.
        # Now covered by ingressToEndpointRule.
        # for agent in agents:
        #     ...

        # Pattern 2: Indirect exfiltration (sensitive agent → exfil agent)
        # DISABLED: Often duplicates ingressToEndpointRule paths without adding value.
        # for sensitive_id in sensitive_agents:
        #     # Find paths from sensitive agent to exfil agents
        #     downstream = graph['forward'].get(sensitive_id, [])
        #
        #     for next_agent in downstream:
        #         if next_agent in exfil_agents:
        #             # Found exfiltration path!
        #             exfil_tool = self._get_exfil_tool(next_agent, tool_edges)
        #             sensitive_tool = self._get_sensitive_tool(sensitive_id, tool_edges)
        #
        #             edge_id = self._find_edge_id(graph, sensitive_id, next_agent)
        #
        #             results.append(RuleResult(
        #                 rule_name="indirectDataExfiltration",
        #                 rule_id="data_exfiltration_chain",
        #                 owasp_category="ASI01+ASI02",
        #                 title="Indirect Data Exfiltration Path",
        #                 description=f"Sensitive data from '{self._get_agent_name(agents, sensitive_id)}' (via {sensitive_tool}) flows to '{self._get_agent_name(agents, next_agent)}', which can exfiltrate via {exfil_tool}.",
        #                 agents_involved=[sensitive_id, next_agent],
        #                 steps=[
        #                     AttackStep(sensitive_id, "agent", "sensitive_data_access",
        #                                f"Accesses sensitive data via {sensitive_tool}"),
        #                     AttackStep(next_agent, "agent", "data_exfiltration",
        #                                f"Receives data and can exfiltrate via {exfil_tool}"),
        #                 ],
        #                 base_cvss=7.2,  # Higher for multi-hop
        #                 path_nodes=[sensitive_id, next_agent, f"tool:{exfil_tool}"],
        #                 path_edges=[edge_id] if edge_id else [],
        #             ))

        return results

    def _find_edge_id(self, graph, source, target):
        """Find edge ID between two agents."""
        for edge_id, edge in graph['edges'].items():
            if edge['caller_agent_id'] == source and edge['callee_agent_id'] == target:
                return edge_id
        return None

    def _get_agent_name(self, agents, agent_id):
        """Get agent display name by ID."""
        for agent in agents:
            if agent['agent_id'] == agent_id:
                return agent['name']
        return agent_id

    def _get_exfil_tool(self, agent_id, tool_edges):
        """Get exfiltration tool name for agent."""
        for edge in tool_edges:
            if edge['agent_id'] == agent_id and edge['tool_category'] in EXFIL_CATEGORIES:
                return edge['tool_name']
        return "external tool"

    def _get_sensitive_tool(self, agent_id, tool_edges):
        """Get sensitive data tool name for agent."""
        for edge in tool_edges:
            if edge['agent_id'] == agent_id and edge['tool_category'] in SENSITIVE_DATA_CATEGORIES:
                if any(pattern in edge['tool_name'].lower() for pattern in SENSITIVE_TOOL_PATTERNS):
                    return edge['tool_name']
        return "sensitive tool"
