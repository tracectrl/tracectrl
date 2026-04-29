"""Guardrail registry API — list and per-agent endpoints."""

import logging
from fastapi import APIRouter, HTTPException

from engine.db.guardrail_registry import get_guardrail_registry
from engine.api.models import GuardrailRegistration

logger = logging.getLogger(__name__)
router = APIRouter(tags=["guardrails"])


@router.get("/guardrails", response_model=list[GuardrailRegistration])
async def list_guardrails(agent_id: str | None = None):
    try:
        return get_guardrail_registry(agent_id=agent_id)
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/agents/{agent_id}/guardrails",
    response_model=list[GuardrailRegistration],
)
async def list_agent_guardrails(agent_id: str):
    try:
        return get_guardrail_registry(agent_id=agent_id)
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")
