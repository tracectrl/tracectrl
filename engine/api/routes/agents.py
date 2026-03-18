"""Agents API routes — agent inventory and tools."""

from fastapi import APIRouter, HTTPException
from engine.db.inventory import get_all_agents, get_tools_for_agent
from engine.api.models import AgentSummary, AgentTool

router = APIRouter(tags=["agents"])


@router.get("/agents", response_model=list[AgentSummary])
async def list_agents(service: str | None = None):
    try:
        return get_all_agents(service=service)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_id}/tools", response_model=list[AgentTool])
async def agent_tools(agent_id: str):
    try:
        return get_tools_for_agent(agent_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
