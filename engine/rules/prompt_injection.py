"""vulnerableToPromptInjection (ASI01) — CVSS 7.2

Fires when: agent has tool edges with call_contexts containing external > 0
AND agent has no human_interaction tool (no guardrail).

Now includes multi-hop path detection to show how external input flows
through agent chains to reach high-risk tools.
"""

import json
from engine.rules.base import BaseRule, RuleResult, AttackStep


class PromptInjectionRule(BaseRule):

    def evaluate(self, agents, tool_edges, agent_edges):
        results = []

        # Step 1: Find directly vulnerable agents (have external input + no guardrails)
        vulnerable_agents = {}  # {agent_id: {name, external_tool, edge_id}}

        for agent in agents:
            agent_id = agent["agent_id"]
            agent_tools = [e for e in tool_edges if e["agent_id"] == agent_id]

            has_external_input = False
            has_guardrail = False
            external_tool = None
            external_edge_id = None

            for edge in agent_tools:
                tool_category = edge["tool_category"]
                contexts = json.loads(edge["call_contexts"]) if isinstance(edge["call_contexts"], str) else edge["call_contexts"]
                if isinstance(contexts, dict) and contexts.get("external", 0) > 0:
                    has_external_input = True
                    if not external_tool:  # Capture first external tool
                        external_tool = edge["tool_name"]
                        external_edge_id = edge["edge_id"]
                if tool_category == "human_interaction":
                    has_guardrail = True

            if has_external_input and not has_guardrail:
                vulnerable_agents[agent_id] = {
                    'name': agent['name'],
                    'external_tool': external_tool,
                    'edge_id': external_edge_id
                }

        if not vulnerable_agents:
            return results

        # Step 2: Build bidirectional graph for path analysis
        graph = self.build_bidirectional_graph(agent_edges)

        # Find high-risk tool categories
        HIGH_RISK_CATEGORIES = {'code_execution', 'email', 'file_system', 'payment', 'external_api'}
        high_risk_agents = self.find_agents_with_tools(agents, tool_edges, categories=HIGH_RISK_CATEGORIES)

        # Step 3: Build attack paths for each vulnerable agent
        for vuln_agent_id, vuln_info in vulnerable_agents.items():
            # Get agents that call this vulnerable agent (data sources)
            callers = graph['backward'].get(vuln_agent_id, [])

            # Single-agent finding (no multi-hop path)
            # DISABLED: Single-agent warnings without showing full attack path to impact.
            # These are configuration issues, not attack paths. Now covered by ingressToEndpointRule.
            # if not callers:
            #     results.append(RuleResult(
            #         ...
            #     ))
            #     continue
            if not callers:
                continue

            # Multi-hop path detection
            # DISABLED: Creates "indirect" attack paths without showing ingress source.
            # for caller_id in callers:
            #     # Check if caller reaches high-risk agents downstream
            #     downstream_paths = self.find_downstream_agents(caller_id, graph, max_hops=2)
            #
            #     for path in downstream_paths:
            #         # Check if any agent in path has high-risk tools
            #         has_risk = any(agent in high_risk_agents for agent in path)
            #
            #         if has_risk and vuln_agent_id in path:
            #             # Found attack chain: Caller → VulnAgent (with external) → ... → HighRiskAgent
            #             # Build path with return edges
            #             full_path = [caller_id, vuln_agent_id]  # Caller delegates to vuln agent
            #             path_edges = [self._find_edge_id(graph, caller_id, vuln_agent_id)]
            #
            #             # Add return edge (vuln agent returns to caller)
            #             if caller_id not in full_path[1:]:
            #                 full_path.append(caller_id)
            #                 path_edges.append(self._find_edge_id(graph, vuln_agent_id, caller_id, is_return=True))
            #
            #             # Add downstream high-risk agent
            #             risk_agent = next((a for a in path if a in high_risk_agents and a != caller_id), None)
            #             if risk_agent and risk_agent not in full_path:
            #                 full_path.append(risk_agent)
            #                 path_edges.append(self._find_edge_id(graph, caller_id, risk_agent))
            #
            #             results.append(RuleResult(
            #                 rule_name="indirectPromptInjection",
            #                 rule_id="prompt_injection_chain",
            #                 owasp_category="ASI01",
            #                 title="Indirect Prompt Injection via Agent Chain",
            #                 description=f"External input flows through '{vuln_info['name']}' back to '{self._get_agent_name(agents, caller_id)}', which can execute high-risk actions. Compromised data can influence downstream behavior.",
            #                 agents_involved=list(set(full_path)),
            #                 steps=[
            #                     AttackStep(caller_id, "agent", "orchestration",
            #                                f"Agent delegates to {vuln_info['name']}"),
            #                     AttackStep(vuln_agent_id, "agent", "no_input_sanitisation",
            #                                f"Processes external input without sanitization"),
            #                     AttackStep(caller_id, "agent", "data_flow_return",
            #                                f"Receives compromised data back"),
            #                     AttackStep(risk_agent, "agent", "high_risk_action",
            #                                f"Executes high-risk operations") if risk_agent else None,
            #                 ],
            #                 base_cvss=7.8,  # Higher for multi-hop
            #                 path_nodes=full_path,
            #                 path_edges=[e for e in path_edges if e],
            #             ))

        return results

    def _find_edge_id(self, graph, source, target, is_return=False):
        """Find edge ID between two agents. For return edges, use special marker."""
        for edge_id, edge in graph['edges'].items():
            if edge['caller_agent_id'] == source and edge['callee_agent_id'] == target:
                return f"{edge_id}_return" if is_return else edge_id
        return None

    def _get_agent_name(self, agents, agent_id):
        """Get agent display name by ID."""
        for agent in agents:
            if agent['agent_id'] == agent_id:
                return agent['name']
        return agent_id
