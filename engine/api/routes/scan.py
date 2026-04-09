"""Scan API routes — trigger scans and retrieve results."""
from fastapi import APIRouter, HTTPException
from engine.db.scan_results import get_scan_results, get_latest_scan, list_scans

router = APIRouter(tags=["scan"])


@router.get("/scans")
async def list_all_scans():
    """List all scans with summary counts."""
    try:
        return list_scans()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scans/latest")
async def latest_scan():
    """Get results from the most recent scan."""
    try:
        results = get_latest_scan()
        if not results:
            return {"scan_id": None, "results": []}
        return {"scan_id": results[0]["scan_id"], "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scans/{scan_id}")
async def scan_detail(scan_id: str):
    """Get results for a specific scan."""
    try:
        results = get_scan_results(scan_id)
        if not results:
            raise HTTPException(status_code=404, detail="Scan not found")
        return {"scan_id": scan_id, "results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
