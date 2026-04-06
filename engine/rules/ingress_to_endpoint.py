"""Ingress-to-Endpoint Attack Path Detection Rule.

Traces potential attack paths from untrusted sources (external ingress + compromised tools)
to high-risk action endpoints using multi-hop graph traversal.

Detects three classes of attack vectors:
1. Malicious external data (upload, email, webhook)
2. Compromised web tools (browse_website, web_search)
3. Compromised external MCP services (check_sanctions, etc.)

Endpoints are high-risk actions: send_email, execute_payment, write_file, execute_code.
"""

import hashlib
from collections import deque
from engine.rules.base import BaseRule, RuleResult, AttackStep
from engine.db.client import execute


# Generic tool direction inference (fallback if SDK doesn't provide it)
def _is_untrusted_input(tool_name: str, tool_category: str = "") -> bool:
    """Determine if a tool is an UNTRUSTED input source.

    Includes both:
    1. Passive receivers (webhooks, uploads, handlers)
    2. Active fetchers from untrusted external sources (MCP tools, web scrapers)
    """
    name_lower = tool_name.lower()

    # UNTRUSTED INPUT Type 1: Passive receivers of external data
    # These are endpoints where external actors can PUSH data TO the system
    passive_receiver_patterns = [
        "handler", "endpoint", "receiver", "listener", "webhook",
        "upload", "inbound", "accept", "intake", "receive",
        "inbox",  # Email inbox receivers
    ]

    if any(pattern in name_lower for pattern in passive_receiver_patterns):
        return True

    # UNTRUSTED INPUT Type 2: Active fetchers from untrusted external sources
    # These are tools that PULL data from third-party services that could be compromised
    # MCP tools, compliance checks, web scrapers, etc.
    risky_external_patterns = [
        # Compliance/validation from third parties (MCP tools)
        "sanction", "compliance", "kyc", "aml", "verify_", "validate_",
        # Web content fetching (untrusted web sources)
        "browse", "scrape", "crawl", "web_search", "search_web", "fetch_url",
        # External data lookups
        "lookup_external", "query_external", "third_party",
    ]

    # Check if tool name suggests it's fetching from untrusted external sources
    if any(pattern in name_lower for pattern in risky_external_patterns):
        # Exclude trusted internal tools (Notion, internal databases, policies)
        trusted_internal_patterns = ["notion", "policy", "_internal", "read_database"]
        if not any(pattern in name_lower for pattern in trusted_internal_patterns):
            return True

    return False


def _infer_tool_direction(tool_name: str) -> str:
    """Infer if a tool is input (ingress) or output (egress) based on its name.

    Note: This is for general direction, not trust level. Use _is_untrusted_input()
    to specifically identify passive receivers of external untrusted data.
    """
    name_lower = tool_name.lower()

    # INPUT patterns - data coming IN (both trusted fetches and untrusted receives)
    if any(k in name_lower for k in ["receive", "fetch", "get_", "read_", "check_", "poll",
                                      "listen", "watch", "handler", "endpoint", "inbound",
                                      "retrieve", "download", "pull", "import", "load", "inbox"]):
        return "input"

    # OUTPUT patterns - data going OUT
    if any(k in name_lower for k in ["send", "post", "put", "push", "publish", "emit",
                                      "write", "create", "execute", "run", "call", "invoke",
                                      "trigger", "dispatch", "submit", "export", "transmit",
                                      "deliver", "forward", "outbound"]):
        return "output"

    return "internal"


# Risk categorization using tool categories + direction
UNTRUSTED_INGRESS = {
    "upload": "malicious_file_upload",
    "email": "malicious_email_attachment",
    "webhook": "compromised_webhook_data",
    "manual": "unvalidated_external_input",
}

# Categories that can be untrusted INPUT sources (when direction = input)
UNTRUSTED_INPUT_CATEGORIES = {
    "external_api",  # HTTP handlers, webhook receivers, API endpoints
    "file_system",   # File upload handlers, file readers
    "email",         # Email receivers (inbox checkers)
}

# Categories that are HIGH-RISK OUTPUTS (when direction = output)
HIGH_RISK_OUTPUT_CATEGORIES = {
    "email": "data_exfiltration",           # send_email
    "external_api": "data_exfiltration",    # HTTP POST, API calls out
    "code_execution": "arbitrary_code_execution",  # exec, eval, shell
    "file_system": "system_tampering",      # write_file, delete_file
}

# Generic patterns to identify high-risk agents by name/role (domain-agnostic)
HIGH_RISK_AGENT_PATTERNS = [
    # Financial/Payment operations
    (["payment", "billing", "transaction", "financial", "bank", "transfer", "invoice"], "financial_operations"),
    # Privileged/Admin operations
    (["admin", "root", "privileged", "sudo", "superuser"], "privileged_access"),
    # Sensitive data handlers
    (["auth", "credential", "secret", "password", "token"], "credential_access"),
    # System operations
    (["deploy", "provision", "infrastructure", "system"], "system_modification"),
]


def _infer_agent_risk_from_name(agent_name: str, agent_role: str = "") -> tuple[bool, str]:
    """Determine if an agent is inherently high-risk based on name/role patterns.

    Returns:
        (is_risky, impact_type)
    """
    combined = f"{agent_name.lower()} {agent_role.lower()}"

    for patterns, impact in HIGH_RISK_AGENT_PATTERNS:
        if any(pattern in combined for pattern in patterns):
            return (True, impact)

    return (False, "")


class IngressToEndpointRule(BaseRule):
    """Detect attack paths from untrusted sources to high-risk actions."""

    def evaluate(self, agents: list[dict], tool_edges: list[dict],
                 agent_edges: list[dict], **kwargs) -> list[RuleResult]:
        """
        Find all paths from untrusted sources to high-risk action endpoints.

        Strategy:
        1. Identify all untrusted source nodes (ingress + compromised tools)
        2. Identify all high-risk action nodes (dangerous tools)
        3. Build agent delegation graph
        4. BFS from each source to find paths to endpoints
        5. Return RuleResult for each discovered attack path
        """
        results = []

        # Step 1: Identify untrusted sources (ingress triggers)
        untrusted_sources = self._get_ingress_sources()

        # Step 2: Identify agents using untrusted web/MCP tools
        untrusted_tool_agents = self._find_agents_with_untrusted_tools(tool_edges)

        # Step 3: Identify agents with high-risk actions (tools or inherent risk)
        high_risk_agents = self._find_agents_with_high_risk_actions(tool_edges, agents)

        if not untrusted_sources and not untrusted_tool_agents:
            # No untrusted sources found
            return []

        if not high_risk_agents:
            # No high-risk endpoints found
            return []

        # Step 4: Build bidirectional agent graph
        graph = self.build_bidirectional_graph(agent_edges)

        # Step 5: Find paths from untrusted sources to high-risk endpoints
        # 5a. Paths starting from external ingress
        for source in untrusted_sources:
            source_agent = source["target_agent_id"]
            trigger_type = source["trigger_type"]
            attack_vector = UNTRUSTED_INGRESS.get(trigger_type, "external_input")

            if not source_agent:
                continue

            paths = self._find_paths_to_endpoints(
                source_agent, high_risk_agents, graph, tool_edges, max_hops=5
            )

            for path_info in paths:
                result = self._build_attack_path_result(
                    source_node=f"ingress:{trigger_type}",
                    source_type="external_ingress",
                    attack_vector=attack_vector,
                    path_info=path_info,
                    agent_edges=agent_edges,
                )
                if result:
                    results.append(result)

        # 5b. Paths starting from agents using untrusted tools
        for tool_source in untrusted_tool_agents:
            agent_id = tool_source["agent_id"]
            tool_name = tool_source["tool_name"]
            attack_vector = tool_source["attack_vector"]

            paths = self._find_paths_to_endpoints(
                agent_id, high_risk_agents, graph, tool_edges, max_hops=4
            )

            for path_info in paths:
                result = self._build_attack_path_result(
                    source_node=f"{agent_id}:{tool_name}",
                    source_type="compromised_tool",
                    attack_vector=attack_vector,
                    path_info=path_info,
                    agent_edges=agent_edges,
                )
                if result:
                    results.append(result)

        return results

    def _get_ingress_sources(self) -> list[dict]:
        """Fetch external ingress triggers from the database."""
        query = """
            SELECT DISTINCT
                if(SpanAttributes['tracectrl.trigger_type'] != '',
                   SpanAttributes['tracectrl.trigger_type'],
                   JSONExtractString(SpanAttributes['metadata'], 'tracectrl.trigger_type')
                ) AS trigger_type,
                SpanAttributes['tracectrl.agent.id'] AS agent_id,
                SpanAttributes['agno.agent.id'] AS agno_agent_id,
                SpanName,
                SpanId
            FROM otel_traces
            WHERE (SpanAttributes['tracectrl.ingress'] = 'True'
                   OR SpanAttributes['tracectrl.ingress'] = 'true'
                   OR JSONExtractString(SpanAttributes['metadata'], 'tracectrl.ingress') = 'true')
        """
        rows = execute(query)

        from engine.db.topology import _get_child_agent_id

        sources = []
        for row in rows:
            trigger_type = row[0] or "external"
            agent_id = row[1] or row[2]
            span_name = row[3]
            span_id = row[4]

            # Only include untrusted external triggers
            if trigger_type not in UNTRUSTED_INGRESS:
                continue

            # Derive agent ID if not set
            if not agent_id:
                if span_name and span_name.startswith("ingress."):
                    agent_id = _get_child_agent_id(span_id)

            if agent_id:
                sources.append({
                    "trigger_type": trigger_type,
                    "target_agent_id": agent_id,
                })

        return sources

    def _find_agents_with_untrusted_tools(self, tool_edges: list[dict]) -> list[dict]:
        """Find agents using untrusted INPUT tools (passive receivers + risky external fetchers)."""
        untrusted = []

        for edge in tool_edges:
            tool_name = edge["tool_name"]
            agent_id = edge["agent_id"]
            tool_category = edge.get("tool_category", "internal_api")

            # Check if this is an UNTRUSTED input (includes both passive receivers and risky fetchers)
            is_untrusted = _is_untrusted_input(tool_name, tool_category)

            # Flag if untrusted (pattern-based detection is enough, don't strictly require category)
            # But skip if it's clearly an internal trusted tool
            if is_untrusted:
                # Determine attack vector based on tool pattern
                if any(p in tool_name.lower() for p in ["sanction", "compliance", "kyc", "aml", "verify"]):
                    attack_vector = "compromised_compliance_service"
                elif any(p in tool_name.lower() for p in ["browse", "scrape", "search", "fetch_url"]):
                    attack_vector = "compromised_web_content"
                elif tool_category == "file_system" or "upload" in tool_name.lower():
                    attack_vector = "malicious_file_input"
                elif tool_category == "email" or "inbox" in tool_name.lower():
                    attack_vector = "malicious_email_content"
                elif "webhook" in tool_name.lower() or "handler" in tool_name.lower():
                    attack_vector = "compromised_webhook_data"
                else:
                    attack_vector = "compromised_external_data_source"

                untrusted.append({
                    "agent_id": agent_id,
                    "tool_name": tool_name,
                    "attack_vector": attack_vector,
                })

        return untrusted

    def _find_agents_with_high_risk_actions(self, tool_edges: list[dict], agents: list[dict]) -> dict[str, list[dict]]:
        """Find agents with high-risk OUTPUT action tools OR inherently risky agents.

        Returns {agent_id: [tool_info]}.
        """
        high_risk = {}

        # 1. Check for agents with high-risk OUTPUT tools (using categories)
        for edge in tool_edges:
            tool_name = edge["tool_name"]
            agent_id = edge["agent_id"]
            tool_category = edge.get("tool_category", "internal_api")

            # Infer direction from tool name
            direction = _infer_tool_direction(tool_name)

            # Only consider OUTPUT tools from high-risk categories
            if direction == "output" and tool_category in HIGH_RISK_OUTPUT_CATEGORIES:
                impact = HIGH_RISK_OUTPUT_CATEGORIES[tool_category]

                if agent_id not in high_risk:
                    high_risk[agent_id] = []

                high_risk[agent_id].append({
                    "tool_name": tool_name,
                    "impact": impact,
                    "tool_category": tool_category,
                })

        # 2. Check for inherently high-risk agents by name/role patterns
        for agent in agents:
            agent_id = agent["agent_id"]
            agent_name = agent.get("name", agent_id)
            agent_role = agent.get("role", "")

            is_risky, impact = _infer_agent_risk_from_name(agent_name, agent_role)

            if is_risky and agent_id not in high_risk:
                # Add agent as a virtual endpoint (the agent itself is the risk)
                high_risk[agent_id] = []
                high_risk[agent_id].append({
                    "tool_name": f"{agent_id}_operations",
                    "impact": impact,
                    "is_agent_endpoint": True,  # Flag: agent itself is the endpoint
                })

        return high_risk

    def _find_paths_to_endpoints(self, start_agent: str, high_risk_agents: dict,
                                  graph: dict, tool_edges: list[dict],
                                  max_hops: int) -> list[dict]:
        """
        BFS to find all paths from start_agent to any agent with high-risk tools.

        Returns list of dicts:
        [
            {
                "agent_path": [agent1, agent2, ...],
                "edge_path": [edge_id1, edge_id2, ...],
                "endpoint_agent": agent_id,
                "endpoint_tools": [tool_info, ...]
            }
        ]
        """
        paths = []
        queue = deque([(start_agent, [start_agent], [])])  # (current, agent_path, edge_path)
        visited = set()

        while queue:
            current, agent_path, edge_path = queue.popleft()

            if len(agent_path) > max_hops:
                continue

            # Check if current agent has high-risk tools
            if current in high_risk_agents and current != start_agent:
                paths.append({
                    "agent_path": agent_path,
                    "edge_path": edge_path,
                    "endpoint_agent": current,
                    "endpoint_tools": high_risk_agents[current],
                })
                # Continue searching for longer paths
                continue

            # Mark as visited for this path length to avoid infinite loops
            visit_key = (current, len(agent_path))
            if visit_key in visited:
                continue
            visited.add(visit_key)

            # Explore downstream agents
            for next_agent in graph["forward"].get(current, []):
                # Find the edge_id for this delegation
                edge_id = None
                for edge in graph["edges"].values():
                    if edge["caller_agent_id"] == current and edge["callee_agent_id"] == next_agent:
                        edge_id = edge["edge_id"]
                        break

                new_agent_path = agent_path + [next_agent]
                new_edge_path = edge_path + ([edge_id] if edge_id else [])
                queue.append((next_agent, new_agent_path, new_edge_path))

        return paths

    def _build_attack_path_result(self, source_node: str, source_type: str,
                                   attack_vector: str, path_info: dict,
                                   agent_edges: list[dict]) -> RuleResult | None:
        """Build RuleResult from a discovered attack path."""
        agent_path = path_info["agent_path"]
        edge_path = path_info["edge_path"]
        endpoint_agent = path_info["endpoint_agent"]
        endpoint_tools = path_info["endpoint_tools"]

        if not agent_path or not endpoint_tools:
            return None

        # Build path_nodes using ACTUAL graph node IDs (not virtual composite IDs)
        path_nodes = []
        path_edges = []

        # Step 1: Add source and edges
        if source_node.startswith("ingress:"):
            # External ingress source
            path_nodes.append(source_node)  # ingress:upload, etc. (actual graph node)
            # Edge: ingress → first_agent
            ingress_edge_id = hashlib.md5(f"{source_node}:{agent_path[0]}".encode()).hexdigest()[:16]
            path_edges.append(ingress_edge_id)
            # Add agent propagation path
            path_nodes.extend(agent_path)
            # Add both delegation and return edges for agent-to-agent paths
            for edge_id in edge_path:
                path_edges.append(edge_id)  # Forward (delegation)
                path_edges.append(f"{edge_id}_return")  # Return (data flow back)
        else:
            # Compromised tool source
            # source_node format: "agent_id:tool_name"
            if ":" in source_node:
                agent_id, tool_name = source_node.split(":", 1)
                tool_node_id = f"tool:{tool_name}"

                # Start with the compromised tool node
                path_nodes.append(tool_node_id)

                # Edge: agent → tool (agent uses compromised tool)
                tool_edge_key = f"{agent_id}:{tool_name}"
                tool_edge_id = hashlib.md5(tool_edge_key.encode()).hexdigest()[:16]
                path_edges.append(tool_edge_id)

                # Edge: tool → agent (return - ATTACK VECTOR: malicious data flows back)
                path_edges.append(f"{tool_edge_id}_return")

                # Add the agent path (starting with the agent that uses the compromised tool)
                path_nodes.extend(agent_path)

                # Add both delegation and return edges for agent-to-agent paths
                for edge_id in edge_path:
                    path_edges.append(edge_id)  # Forward (delegation)
                    path_edges.append(f"{edge_id}_return")  # Return (data flow back)

        # Step 3: Add endpoint tools as actual graph nodes
        for tool in endpoint_tools:
            # Skip virtual agent endpoints
            if tool.get("is_agent_endpoint"):
                continue

            tool_node_id = f"tool:{tool['tool_name']}"
            path_nodes.append(tool_node_id)

            # Edge: endpoint_agent → tool (forward)
            tool_edge_key = f"{endpoint_agent}:{tool['tool_name']}"
            tool_edge_id = hashlib.md5(tool_edge_key.encode()).hexdigest()[:16]
            path_edges.append(tool_edge_id)

            # Edge: tool → endpoint_agent (return - data flows back)
            tool_return_edge_id = f"{tool_edge_id}_return"
            path_edges.append(tool_return_edge_id)

        # Build attack steps
        steps = []

        # Step 1: Untrusted source
        if source_type == "external_ingress":
            steps.append(AttackStep(
                node_id=source_node,
                node_type="ingress",
                vulnerability=attack_vector,
                description=f"Untrusted data enters via {source_node}",
            ))
        else:
            # Compromised tool source
            if ":" in source_node:
                agent_id, tool_name = source_node.split(":", 1)
                steps.append(AttackStep(
                    node_id=f"tool:{tool_name}",
                    node_type="tool",
                    vulnerability=attack_vector,
                    description=f"Agent {agent_id} uses compromised tool {tool_name}",
                ))

        # Step 2: Propagation through agents
        for i, agent_id in enumerate(agent_path):
            steps.append(AttackStep(
                node_id=agent_id,
                node_type="agent",
                vulnerability="prompt_injection_propagation",
                description=f"Agent {agent_id} processes untrusted data (hop {i+1})",
            ))

        # Step 3: High-risk action endpoints
        for tool in endpoint_tools:
            if tool.get("is_agent_endpoint"):
                # Agent itself is the endpoint
                steps.append(AttackStep(
                    node_id=endpoint_agent,
                    node_type="agent",
                    vulnerability=tool["impact"],
                    description=f"High-risk agent endpoint: {endpoint_agent} handles {tool['impact']}",
                ))
            else:
                # Tool is the endpoint
                steps.append(AttackStep(
                    node_id=f"tool:{tool['tool_name']}",
                    node_type="tool",
                    vulnerability=tool["impact"],
                    description=f"High-risk action: {tool['tool_name']} → {tool['impact']}",
                ))

        # Determine rule metadata
        impact = endpoint_tools[0]["impact"]
        hops = len(agent_path)
        first_tool = endpoint_tools[0]
        is_agent_endpoint = first_tool.get("is_agent_endpoint", False)

        # Build title and description
        if source_type == "external_ingress":
            if is_agent_endpoint:
                title = f"Attack path from {source_node} to high-risk agent {endpoint_agent}"
                description = (
                    f"Untrusted data from {source_node} ({attack_vector}) propagates through "
                    f"{hops} agent(s) and reaches high-risk agent {endpoint_agent} "
                    f"({impact}). Malicious input could influence sensitive operations."
                )
            else:
                title = f"Attack path from {source_node} to {impact}"
                description = (
                    f"Untrusted data from {source_node} ({attack_vector}) propagates through "
                    f"{hops} agent(s) and reaches high-risk action {first_tool['tool_name']} "
                    f"({impact}). Malicious input could be weaponized to exploit downstream actions."
                )
        else:
            if is_agent_endpoint:
                title = f"Attack path via compromised tool to high-risk agent {endpoint_agent}"
                description = (
                    f"Agent uses untrusted tool {source_node} ({attack_vector}) and propagates "
                    f"data through {hops} agent(s) to high-risk agent {endpoint_agent} "
                    f"({impact}). Compromised tool could inject malicious data."
                )
            else:
                title = f"Attack path via compromised tool to {impact}"
                description = (
                    f"Agent uses untrusted tool {source_node} ({attack_vector}) and propagates "
                    f"data through {hops} agent(s) to high-risk action {first_tool['tool_name']} "
                    f"({impact}). Compromised tool could inject malicious data."
                )

        # CVSS base varies by impact
        base_cvss_map = {
            "data_exfiltration": 8.5,
            "financial_fraud": 9.0,
            "financial_operations": 9.0,
            "system_tampering": 7.5,
            "arbitrary_code_execution": 9.5,
            "command_injection": 9.0,
        }
        base_cvss = base_cvss_map.get(impact, 7.0)

        # OWASP category
        owasp_map = {
            "data_exfiltration": "LLM06:SensitiveInformationDisclosure",
            "financial_fraud": "LLM09:Overreliance",
            "financial_operations": "LLM09:Overreliance",
            "system_tampering": "LLM08:ExcessiveAgency",
            "arbitrary_code_execution": "LLM01:PromptInjection",
            "command_injection": "LLM01:PromptInjection",
        }
        owasp = owasp_map.get(impact, "LLM01:PromptInjection")

        rule_id = f"ATK-INGRESS-{impact.upper()}"

        return RuleResult(
            rule_name="ingressToEndpointAttackPath",
            rule_id=rule_id,
            owasp_category=owasp,
            title=title,
            description=description,
            agents_involved=agent_path,
            steps=steps,
            base_cvss=base_cvss,
            path_nodes=path_nodes,
            path_edges=path_edges,
        )
