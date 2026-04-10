"""Scan API routes — trigger scans and retrieve results."""
import logging
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from engine.db.scan_results import get_scan_results, get_latest_scan, list_scans, store_scan_results

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scan"])


class ScanCheckPayload(BaseModel):
    check_id: str
    section: str
    title: str
    severity: str
    passed: bool
    finding: str = ""
    remediation: str = ""
    config_path: str = ""


class ScanUploadPayload(BaseModel):
    scan_path: str
    profile: str = "L1"
    checks: list[ScanCheckPayload]


def _validate_scan_id(scan_id: str) -> None:
    if not re.match(r'^[0-9a-f]{1,12}$', scan_id):
        raise HTTPException(status_code=400, detail="Invalid scan ID format")


@router.post("/scans")
async def upload_scan(payload: ScanUploadPayload):
    """Receive scan results from a remote CLI and store them."""
    try:
        results = [c.model_dump() for c in payload.checks]
        scan_id = store_scan_results(results, payload.scan_path, payload.profile)
        return {"scan_id": scan_id, "stored": len(results)}
    except Exception:
        logger.exception("Failed to store uploaded scan")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scans")
async def list_all_scans():
    """List all scans with summary counts."""
    try:
        return list_scans()
    except Exception:
        logger.exception("Failed to fetch scans")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scans/latest")
async def latest_scan():
    """Get results from the most recent scan."""
    try:
        results = get_latest_scan()
        if not results:
            return {"scan_id": None, "results": []}
        return {"scan_id": results[0]["scan_id"], "results": results}
    except Exception:
        logger.exception("Failed to fetch latest scan")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/scans/{scan_id}")
async def scan_detail(scan_id: str):
    """Get results for a specific scan."""
    _validate_scan_id(scan_id)
    try:
        results = get_scan_results(scan_id)
        if not results:
            raise HTTPException(status_code=404, detail="Scan not found")
        return {"scan_id": scan_id, "results": results}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch scan %s", scan_id)
        raise HTTPException(status_code=500, detail="Internal server error")
