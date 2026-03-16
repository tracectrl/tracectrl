"""Sessions API routes — stub for Sprint 1."""

from fastapi import APIRouter

router = APIRouter(tags=["sessions"])


@router.get("/sessions")
async def list_sessions():
    """Stub: returns empty list. Full implementation in Sprint 2."""
    return []
