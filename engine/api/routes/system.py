"""System routes — health check and config."""

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
