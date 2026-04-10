"""Sessions API routes — session list and span tree."""

from fastapi import APIRouter, HTTPException
from engine.db.sessions import get_session_list, get_trace_spans, get_latest_trace_spans
from engine.api.models import SessionSummary, SpanDetail

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(service: str | None = None):
    try:
        return get_session_list(service=service)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/latest-spans", response_model=list[SpanDetail])
async def latest_spans(service: str | None = None):
    """Returns spans from the most recent trace."""
    try:
        return get_latest_trace_spans(service=service)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{trace_id}/spans", response_model=list[SpanDetail])
async def get_spans(trace_id: str, extra: str | None = None):
    """Get spans for a trace. Pass extra=id1,id2 for merged OpenClaw sessions."""
    try:
        spans = get_trace_spans(trace_id)
        # For merged OpenClaw sessions, also fetch spans from extra trace IDs
        if extra:
            for extra_id in extra.split(","):
                extra_id = extra_id.strip()
                if extra_id:
                    spans.extend(get_trace_spans(extra_id))
        if not spans:
            raise HTTPException(status_code=404, detail="Trace not found")
        # Sort all spans by timestamp
        spans.sort(key=lambda s: s.get("start_ns", 0))
        return spans
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
