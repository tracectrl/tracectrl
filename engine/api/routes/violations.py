"""Guardrail violations API — list, recent, and SSE stream."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from engine.db.violations import (
    get_violations,
    get_violations_since,
    get_latest_inserted_at,
)
from engine.api.models import Violation

logger = logging.getLogger(__name__)
router = APIRouter(tags=["violations"])


@router.get("/violations", response_model=list[Violation])
async def list_violations(
    limit: int = 50,
    agent_id: str | None = None,
    severity: str | None = None,
):
    try:
        return get_violations(limit=limit, agent_id=agent_id, severity=severity)
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/violations/recent", response_model=list[Violation])
async def recent_violations(limit: int = 20):
    try:
        return get_violations(limit=limit)
    except Exception:
        logger.exception("Internal error")
        raise HTTPException(status_code=500, detail="Internal server error")


def _violation_to_jsonable(v: dict) -> dict:
    out = {k: v[k] for k in (
        "violation_id", "trace_id", "span_id", "eval_span_id", "agent_id",
        "guardrail_name", "judge_model", "decision", "reason", "evidence",
        "severity",
    )}
    obs = v.get("observed_at")
    out["observed_at"] = obs.isoformat() if isinstance(obs, datetime) else str(obs)
    out["provider"] = v.get("provider", "judge_llm")
    return out


@router.get("/violations/stream")
async def stream_violations(request: Request):
    """Server-Sent Events stream of guardrail violations.

    On connect:
      - Emits `event: init` with the last 20 violations as a JSON array.
      - Polls every 2s for new rows (`inserted_at > last_seen`) and emits each
        as `event: violation`.
      - Emits a `: heartbeat` comment every 15 seconds to keep the connection
        alive through proxies.
    """
    poll_interval = 2.0
    heartbeat_interval = 15.0

    async def event_gen():
        # IMPORTANT: read the watermark BEFORE fetching the init payload.
        # Any row inserted between these two reads is both included in `init`
        # AND picked up on the first poll, so the client receives it twice —
        # but the client de-dupes on violation_id, so this is harmless and
        # strictly safer than the reverse (a row inserted between init and
        # watermark would otherwise be silently dropped if its observed_at
        # placed it outside the top-20-by-recency cut).
        try:
            last_seen = get_latest_inserted_at()
        except Exception:
            logger.exception("violations/stream: failed to read watermark")
            # tz-aware to match the comparison against tz-aware
            # `_inserted_at` values from get_violations_since
            last_seen = datetime(1970, 1, 1, tzinfo=timezone.utc)

        try:
            initial = get_violations(limit=20)
            init_payload = [_violation_to_jsonable(v) for v in initial]
            yield f"event: init\ndata: {json.dumps(init_payload)}\n\n"
        except Exception:
            logger.exception("violations/stream: failed to emit init payload")
            yield "event: init\ndata: []\n\n"

        last_heartbeat = asyncio.get_event_loop().time()

        while True:
            if await request.is_disconnected():
                break

            try:
                new_rows = get_violations_since(last_seen, limit=100)
            except Exception:
                logger.exception("violations/stream: poll failed")
                new_rows = []

            for v in new_rows:
                inserted = v.pop("_inserted_at", None)
                if isinstance(inserted, datetime) and inserted > last_seen:
                    last_seen = inserted
                payload = _violation_to_jsonable(v)
                yield f"event: violation\ndata: {json.dumps(payload)}\n\n"

            now = asyncio.get_event_loop().time()
            if now - last_heartbeat >= heartbeat_interval:
                yield ": heartbeat\n\n"
                last_heartbeat = now

            await asyncio.sleep(poll_interval)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers=headers,
    )
