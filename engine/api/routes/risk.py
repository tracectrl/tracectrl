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
            SELECT agent_id, severity, risk_score, path_nodes
            FROM attack_paths FINAL
            """
        )

        # Aggregate compromised nodes by highest severity
        node_map = {}
        attack_edges = []

        for row in rows:
            agent_id, severity, risk_score, path_nodes = row

            # Track compromised agent node
            if agent_id not in node_map or risk_score > node_map[agent_id]["risk_score"]:
                node_map[agent_id] = {
                    "node_id": agent_id,
                    "severity": severity,
                    "risk_score": risk_score,
                }

            # Build attack edges from path_nodes
            if len(path_nodes) >= 2:
                for i in range(len(path_nodes) - 1):
                    attack_edges.append({
                        "source": path_nodes[i],
                        "target": path_nodes[i + 1],
                        "rule_id": "attack_path",
                        "severity": severity,
                    })

        return {
            "compromised_nodes": list(node_map.values()),
            "attack_edges": attack_edges,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
