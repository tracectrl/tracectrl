"""Base classes for TAGAAI attack graph rules."""

from dataclasses import dataclass, field
from collections import defaultdict
from typing import Set, List, Dict


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

    @staticmethod
    def build_bidirectional_graph(agent_edges: list[dict]) -> dict:
        """Build bidirectional graph from agent edges.

        Returns:
            {
                'forward': {caller_id: [callee_ids...]},  # delegation edges
                'backward': {callee_id: [caller_ids...]},  # return edges (data flow back)
                'edges': {edge_id: edge_dict}
            }
        """
        graph = {
            'forward': defaultdict(list),
            'backward': defaultdict(list),
            'edges': {}
        }
        for edge in agent_edges:
            caller = edge['caller_agent_id']
            callee = edge['callee_agent_id']
            edge_id = edge['edge_id']

            graph['forward'][caller].append(callee)
            graph['backward'][callee].append(caller)
            graph['edges'][edge_id] = edge

        return graph

    @staticmethod
    def find_downstream_agents(start_agent: str, graph: dict, max_hops: int = 3) -> List[List[str]]:
        """Find all agents reachable from start_agent within max_hops.

        Returns list of paths: [[start, agent1], [start, agent1, agent2], ...]
        """
        paths = []
        visited = set()

        def dfs(current: str, path: List[str], hops: int):
            if hops > max_hops:
                return

            if current in visited and len(path) > 1:
                return

            if len(path) > 1:
                paths.append(path[:])

            visited.add(current)

            for neighbor in graph['forward'].get(current, []):
                dfs(neighbor, path + [neighbor], hops + 1)

            visited.discard(current)

        dfs(start_agent, [start_agent], 0)
        return paths

    @staticmethod
    def find_agents_with_tools(agents: list[dict], tool_edges: list[dict],
                               categories: Set[str] = None,
                               tool_patterns: List[str] = None,
                               with_external: bool = False) -> List[str]:
        """Find agents that have tools matching criteria."""
        import json
        matching_agents = set()

        for edge in tool_edges:
            agent_id = edge['agent_id']
            tool_category = edge['tool_category']
            tool_name = edge['tool_name']

            # Check category match
            if categories and tool_category not in categories:
                continue

            # Check tool name pattern match
            if tool_patterns:
                if not any(pattern in tool_name.lower() for pattern in tool_patterns):
                    continue

            # Check external input
            if with_external:
                contexts = edge.get('call_contexts', {})
                if isinstance(contexts, str):
                    contexts = json.loads(contexts)
                if not isinstance(contexts, dict) or contexts.get('external', 0) == 0:
                    continue

            matching_agents.add(agent_id)

        return list(matching_agents)
