"""Agents API routes — agent inventory and tools."""

import logging
from fastapi import APIRouter, HTTPException
from engine.db.inventory import get_all_agents, get_tools_for_agent
from engine.api.models import AgentSummary, AgentTool

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agents"])


@router.get("/agents", response_model=list[AgentSummary])
async def list_agents(service: str | None = None):
    try:
        return get_all_agents(service=service)
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/agents/{agent_id}/tools", response_model=list[AgentTool])
async def agent_tools(agent_id: str):
    try:
        return get_tools_for_agent(agent_id)
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")
