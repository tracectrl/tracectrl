"""Sessions API routes — session list and span tree."""

from fastapi import APIRouter, HTTPException
from engine.db.sessions import get_session_list, get_trace_spans
from engine.api.models import SessionSummary, SpanDetail

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions():
    try:
        return get_session_list()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{trace_id}/spans", response_model=list[SpanDetail])
async def get_spans(trace_id: str):
    try:
        spans = get_trace_spans(trace_id)
        if not spans:
            raise HTTPException(status_code=404, detail="Trace not found")
        return spans
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
