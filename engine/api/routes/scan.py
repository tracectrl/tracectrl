"""Scan API routes — trigger scans and retrieve results."""
import asyncio
import hashlib
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from engine.db.scan_results import (
    get_scan_results, get_latest_scan, list_scans, store_scan_results, get_scan_topology,
    store_scan_run, get_latest_scan_run,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scan"])

_scan_lock = asyncio.Lock()
_scan_jobs: dict[str, dict] = {}  # scan_id → { status, started_at, completed_at, error }


class ScanCheckPayload(BaseModel):
    model_config = {"extra": "ignore"}

    check_id: str
    section: str
    title: str
    severity: str
    passed: bool
    finding: str | None = ""
    remediation: str | None = ""
    config_path: str | None = ""


class ScanUploadPayload(BaseModel):
    scan_path: str
    profile: str = "L1"
    checks: list[ScanCheckPayload]
    topology: dict | None = None


class ValidatePathPayload(BaseModel):
    path: str


class ScanTriggerPayload(BaseModel):
    workspace_path: str
    profile: str = "L1"


class ScanFixPayload(BaseModel):
    workspace_path: str
    check_ids: list[str]


def _validate_scan_id(scan_id: str) -> None:
    if not re.match(r'^[0-9a-f]{1,12}$', scan_id):
        raise HTTPException(status_code=400, detail="Invalid scan ID format")


def _compute_config_hash(workspace_path: str) -> str | None:
    """Compute SHA-256[:16] of openclaw.json content. Returns None if file not accessible."""
    try:
        config_file = Path(workspace_path) / "openclaw.json"
        content = config_file.read_bytes()
        return hashlib.sha256(content).hexdigest()[:16]
    except Exception:
        return None


async def _run_scan_subprocess(workspace_path: str, scan_id: str, profile: str) -> None:
    """Run tracectrl scan in a subprocess and store results."""
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "tracectrl", "scan", workspace_path,
            "--engine-json", "--no-upload", f"--profile={profile}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode not in (0, 1):  # 1 = has criticals, still valid
            raise RuntimeError(f"Scanner exited {proc.returncode}: {stderr.decode()[:500]}")

        import json as _json
        payload = _json.loads(stdout.decode())
        checks = payload.get("checks", [])
        topology = payload.get("topology")
        scan_path = payload.get("scan_path", workspace_path)
        config_hash = _compute_config_hash(workspace_path) or ""

        # store_scan_results generates its own scan_id — capture the stored scan_id
        stored_id = store_scan_results(checks, scan_path, profile, topology=topology)

        # Overwrite the auto-stored scan_run with one that includes the config hash
        store_scan_run(stored_id, workspace_path, profile, config_hash)

        _scan_jobs[scan_id]["status"] = "complete"
        _scan_jobs[scan_id]["stored_scan_id"] = stored_id
        _scan_jobs[scan_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as e:
        logger.exception("Scan subprocess failed for %s", workspace_path)
        _scan_jobs[scan_id]["status"] = "failed"
        _scan_jobs[scan_id]["error"] = str(e)
        _scan_jobs[scan_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        _scan_lock.release()


@router.post("/scans")
async def upload_scan(payload: ScanUploadPayload):
    """Receive scan results from a remote CLI and store them."""
    try:
        results = [{k: (v if v is not None else "") for k, v in c.model_dump().items()} for c in payload.checks]
        scan_id = store_scan_results(results, payload.scan_path, payload.profile, topology=payload.topology)
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
    """Get results from the most recent scan, with config drift detection."""
    try:
        results = get_latest_scan()
        if not results:
            return {"scan_id": None, "results": [], "topology": None,
                    "config_changed": False, "days_since_scan": None}
        scan_id = results[0]["scan_id"]
        topology = get_scan_topology(scan_id)

        # Config drift detection
        config_changed = False
        config_hash_at_scan = ""
        config_hash_current = ""
        days_since_scan = None

        scan_run = get_latest_scan_run()
        if scan_run:
            config_hash_at_scan = scan_run.get("config_hash", "")
            workspace_path = scan_run.get("workspace_path") or results[0].get("openclaw_path", "")
            scanned_at = results[0].get("scanned_at")
            if scanned_at:
                try:
                    if hasattr(scanned_at, 'timestamp'):
                        days_since_scan = (datetime.now(timezone.utc) - scanned_at.replace(tzinfo=timezone.utc)).days
                    else:
                        days_since_scan = (datetime.now(timezone.utc) - datetime.fromisoformat(str(scanned_at)).replace(tzinfo=timezone.utc)).days
                except Exception:
                    pass
            if workspace_path:
                config_hash_current = _compute_config_hash(workspace_path) or ""
                if config_hash_at_scan and config_hash_current:
                    config_changed = config_hash_current != config_hash_at_scan
                elif not config_hash_at_scan:
                    # No hash stored (CLI upload) — can't detect drift
                    config_changed = False

        return {
            "scan_id": scan_id,
            "results": results,
            "topology": topology,
            "config_changed": config_changed,
            "config_hash_at_scan": config_hash_at_scan,
            "config_hash_current": config_hash_current,
            "days_since_scan": days_since_scan,
        }
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
        topology = get_scan_topology(scan_id)
        return {"scan_id": scan_id, "results": results, "topology": topology}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch scan %s", scan_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/scan/validate-path")
async def validate_workspace_path(payload: ValidatePathPayload):
    """Check if a path is a valid OpenClaw workspace."""
    path = payload.path.strip()
    exists = os.path.exists(path)
    json_found = os.path.exists(os.path.join(path, "openclaw.json")) if exists else False
    if not exists:
        return {"valid": False, "openclaw_json_found": False, "path": path, "error": "Path does not exist"}
    if not json_found:
        return {"valid": False, "openclaw_json_found": False, "path": path,
                "error": "Not an OpenClaw workspace (no openclaw.json found)"}
    return {"valid": True, "openclaw_json_found": True, "path": path}


@router.post("/scan/trigger")
async def trigger_scan(payload: ScanTriggerPayload):
    """Trigger a scan from the UI. Returns immediately; poll /scan/status/{scan_id} for completion."""
    workspace_path = payload.workspace_path.strip()
    if not os.path.exists(os.path.join(workspace_path, "openclaw.json")):
        raise HTTPException(status_code=400, detail="Path is not a valid OpenClaw workspace")

    # Prune stale jobs (> 30 min old)
    cutoff = datetime.now(timezone.utc).timestamp() - 1800
    stale = [sid for sid, job in _scan_jobs.items()
             if datetime.fromisoformat(job["started_at"]).timestamp() < cutoff]
    for sid in stale:
        _scan_jobs.pop(sid, None)

    # Non-blocking lock check — return 409 immediately if a scan is already running
    if _scan_lock.locked():
        raise HTTPException(status_code=409, detail="A scan is already running")

    try:
        await asyncio.wait_for(_scan_lock.acquire(), timeout=0.1)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=409, detail="A scan is already running")

    scan_id = str(uuid4())[:12]
    started_at = datetime.now(timezone.utc).isoformat()
    _scan_jobs[scan_id] = {"status": "running", "started_at": started_at,
                           "completed_at": None, "error": None}

    asyncio.create_task(_run_scan_subprocess(workspace_path, scan_id, payload.profile))
    return {"scan_id": scan_id, "status": "running", "started_at": started_at}


@router.get("/scan/status/{scan_id}")
async def scan_status(scan_id: str):
    """Poll for scan completion status."""
    job = _scan_jobs.get(scan_id)
    if not job:
        raise HTTPException(status_code=404, detail="Scan job not found (may have expired)")
    return {
        "scan_id": scan_id,
        "status": job["status"],
        "started_at": job["started_at"],
        "completed_at": job.get("completed_at"),
        "error": job.get("error"),
        "stored_scan_id": job.get("stored_scan_id"),
    }


@router.post("/scan/fix")
async def apply_fixes_endpoint(payload: ScanFixPayload):
    """Apply automated fixes for specified check IDs."""
    import json as _json
    import shutil as _shutil
    try:
        from tracectrl_scanner.fix import AUTOMATED_FIXES
    except ImportError:
        raise HTTPException(status_code=503,
                            detail="Scanner not installed — run: pip install tracectrl-scanner")

    workspace_path = Path(payload.workspace_path.strip())
    config_path = workspace_path / "openclaw.json"

    if not config_path.exists():
        raise HTTPException(status_code=400, detail="openclaw.json not found at workspace path")

    # Load config
    try:
        try:
            import pyjson5
            with open(config_path) as f:
                config = pyjson5.load(f)
        except ImportError:
            config = _json.loads(config_path.read_text())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse openclaw.json: {e}")

    # Backup
    _shutil.copy2(config_path, config_path.with_suffix(".json.bak"))

    applied, skipped, errors = [], [], {}
    for check_id in payload.check_ids:
        if check_id not in AUTOMATED_FIXES:
            skipped.append(check_id)
            continue
        try:
            AUTOMATED_FIXES[check_id](config)
            applied.append(check_id)
        except Exception as e:
            errors[check_id] = str(e)

    # Write back (only if anything was applied)
    if applied:
        try:
            import pyjson5
            with open(config_path, "w") as f:
                f.write(pyjson5.dumps(config, indent=2))
        except ImportError:
            config_path.write_text(_json.dumps(config, indent=2))

    return {"applied": applied, "skipped": skipped, "errors": errors}
