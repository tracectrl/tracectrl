"""Topology API routes."""

from fastapi import APIRouter, HTTPException
from engine.db.topology import get_topology_graph
from engine.db.inventory import get_all_agents, get_agent_by_id

router = APIRouter(tags=["topology"])


@router.get("/topology/graph")
async def topology_graph():
    """Returns the full topology graph: { nodes: [...], edges: [...] }"""
    try:
        return get_topology_graph()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topology/agents/{agent_id}")
async def agent_detail(agent_id: str):
    """Returns full agent record from agent_inventory."""
    agent = get_agent_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("/risk/agents")
async def risk_agents():
    """Basic agent inventory list (risk scoring added in Sprint 2)."""
    return get_all_agents()
