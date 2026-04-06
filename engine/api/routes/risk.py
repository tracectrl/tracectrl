"""Risk API routes — risk summary, attack paths, agent scores."""

from fastapi import APIRouter, HTTPException
from engine.db.client import execute
from engine.db.attack_graph import get_attack_paths, get_agent_risk_scores, get_system_risk
from engine.api.models import AttackPath, AgentRisk, RiskSummary

router = APIRouter(tags=["risk"])


@router.get("/risk/summary", response_model=RiskSummary | None)
async def risk_summary():
    try:
        return get_system_risk()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk/attack-paths", response_model=list[AttackPath])
async def attack_paths(service: str | None = None):
    try:
        return get_attack_paths(service=service)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk/agent-scores", response_model=list[AgentRisk])
async def agent_scores(service: str | None = None):
    try:
        return get_agent_risk_scores(service=service)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/attack-graph/paths")
def get_detailed_attack_paths():
    """Fetch detailed attack paths with full vulnerability info (for findings panel)."""
    try:
        rows = execute(
            """
            SELECT path_id, rule_id, severity, owasp_tag, title, description,
                   agent_id, path_nodes, path_edges, risk_score, detected_at
            FROM attack_paths FINAL
            ORDER BY risk_score DESC
            """
        )

        paths = []
        for row in rows:
            paths.append({
                "path_id": row[0],
                "rule_id": row[1],
                "severity": row[2],
                "owasp_tag": row[3],
                "title": row[4],
                "description": row[5],
                "agent_id": row[6],
                "path_nodes": row[7],
                "path_edges": row[8],
                "risk_score": row[9],
                "detected_at": row[10].isoformat() if row[10] else None,
            })

        return {"paths": paths}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/attack-graph/overlay")
def get_attack_overlay():
    """Build overlay data for Attack Surface mode visualization."""
    try:
        rows = execute(
            """
            SELECT agent_id, severity, risk_score, path_nodes, path_edges
            FROM attack_paths FINAL
            """
        )

        # Get topology edges to map edge IDs to source/target
        topology_edges = {}

        # Fetch agent delegation edges
        agent_edges = execute("SELECT edge_id, caller_agent_id, callee_agent_id FROM topology_agent_edges FINAL")
        for edge_id, source, target in agent_edges:
            topology_edges[edge_id] = {"source": source, "target": target}

        # Fetch tool edges
        tool_edges = execute("SELECT edge_id, agent_id, tool_name FROM topology_tool_edges FINAL")
        for edge_id, agent_id, tool_name in tool_edges:
            topology_edges[edge_id] = {"source": agent_id, "target": f"tool:{tool_name}"}

        # Fetch ingress edges (compute edge IDs same way topology does)
        import hashlib
        from engine.db.topology import _get_child_agent_id

        ingress_triggers = execute(
            """
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
        )
        for trigger_type, agent_id, agno_agent_id, span_name, span_id in ingress_triggers:
            trigger = trigger_type or "external"
            target = agent_id or agno_agent_id

            # Derive agent ID if not set (same logic as rule)
            if not target:
                if span_name and span_name.startswith("ingress."):
                    target = _get_child_agent_id(span_id)

            if target:
                edge_key = f"ingress:{trigger}:{target}"
                edge_id = hashlib.md5(edge_key.encode()).hexdigest()[:16]
                topology_edges[edge_id] = {"source": f"ingress:{trigger}", "target": target}

        # Aggregate compromised nodes by highest severity
        node_map = {}
        attack_edges_map = {}  # Use map to deduplicate edges

        for row in rows:
            agent_id, severity, risk_score, path_nodes, path_edges = row

            # Track compromised agent node
            if agent_id not in node_map or risk_score > node_map[agent_id]["risk_score"]:
                node_map[agent_id] = {
                    "node_id": agent_id,
                    "severity": severity,
                    "risk_score": risk_score,
                }

            # Track all nodes in path as compromised
            for node in path_nodes:
                if node.startswith("tool:") or node.startswith("ingress:"):
                    continue  # Only track agent nodes as compromised
                if node not in node_map or risk_score > node_map[node]["risk_score"]:
                    node_map[node] = {
                        "node_id": node,
                        "severity": severity,
                        "risk_score": risk_score,
                    }

            # Build attack edges from path_edges (actual topology edge IDs)
            if path_edges:
                for edge_id in path_edges:
                    if edge_id in topology_edges:
                        topo_edge = topology_edges[edge_id]
                        edge_key = f"{topo_edge['source']}:{topo_edge['target']}"
                        if edge_key not in attack_edges_map:
                            attack_edges_map[edge_key] = {
                                "source": topo_edge["source"],
                                "target": topo_edge["target"],
                                "rule_id": "attack_path",
                                "severity": severity,
                            }
                        elif severity_rank(severity) > severity_rank(attack_edges_map[edge_key]["severity"]):
                            # Update to higher severity
                            attack_edges_map[edge_key]["severity"] = severity
            else:
                # Fallback: build edges from path_nodes sequentially (old behavior)
                if len(path_nodes) >= 2:
                    for i in range(len(path_nodes) - 1):
                        edge_key = f"{path_nodes[i]}:{path_nodes[i+1]}"
                        if edge_key not in attack_edges_map:
                            attack_edges_map[edge_key] = {
                                "source": path_nodes[i],
                                "target": path_nodes[i + 1],
                                "rule_id": "attack_path",
                                "severity": severity,
                            }

        return {
            "compromised_nodes": list(node_map.values()),
            "attack_edges": list(attack_edges_map.values()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def severity_rank(severity: str) -> int:
    """Return numeric rank for severity comparison."""
    ranks = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
    return ranks.get(severity, 0)
