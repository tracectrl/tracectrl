"""Risk API routes — risk summary, attack paths, agent scores."""

import logging
from fastapi import APIRouter, HTTPException
from engine.db.attack_graph import get_attack_paths, get_agent_risk_scores, get_system_risk
from engine.api.models import AttackPath, AgentRisk, RiskSummary

logger = logging.getLogger(__name__)
router = APIRouter(tags=["risk"])


@router.get("/risk/summary", response_model=RiskSummary | None)
async def risk_summary():
    try:
        return get_system_risk()
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/risk/attack-paths", response_model=list[AttackPath])
async def attack_paths(service: str | None = None):
    try:
        return get_attack_paths(service=service)
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/risk/agent-scores", response_model=list[AgentRisk])
async def agent_scores(service: str | None = None):
    try:
        return get_agent_risk_scores(service=service)
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")
