"""Scan result storage and retrieval."""
import json as _json
import uuid
from datetime import datetime
from engine.db.client import execute


def store_scan_results(results: list[dict], openclaw_path: str, profile: str, topology: dict | None = None) -> str:
    """Store scan results in ClickHouse. Returns the scan_id."""
    scan_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow()

    rows = [
        (
            scan_id, now, openclaw_path, profile,
            r["check_id"], r["section"], r["title"],
            r["severity"], 1 if r["passed"] else 0,
            r.get("finding", ""), r.get("remediation", ""),
            r.get("config_path", ""),
        )
        for r in results
    ]
    if rows:
        execute("INSERT INTO scan_results VALUES", rows)
    if topology:
        store_scan_topology(scan_id, topology)
    store_scan_run(scan_id, openclaw_path, profile)
    return scan_id


def store_scan_topology(scan_id: str, topology: dict) -> None:
    """Store a topology JSON blob for a scan."""
    execute(
        "INSERT INTO scan_topology (scan_id, created_at, topology_json) VALUES",
        [(scan_id, datetime.utcnow(), _json.dumps(topology, default=str))],
    )


def get_scan_topology(scan_id: str) -> dict | None:
    """Retrieve the topology blob for a scan."""
    rows = execute(
        "SELECT topology_json FROM scan_topology WHERE scan_id = %(scan_id)s LIMIT 1",
        {"scan_id": scan_id},
    )
    if not rows:
        return None
    try:
        return _json.loads(rows[0][0])
    except Exception:
        return None


def get_scan_results(scan_id: str) -> list[dict]:
    """Fetch results for a specific scan."""
    rows = execute(
        """SELECT scan_id, scanned_at, openclaw_path, profile, check_id,
                  section, title, severity, passed, finding, remediation, config_path
           FROM scan_results
           WHERE scan_id = %(scan_id)s
           ORDER BY severity, check_id""",
        {"scan_id": scan_id},
    )
    columns = ["scan_id", "scanned_at", "openclaw_path", "profile", "check_id",
               "section", "title", "severity", "passed", "finding", "remediation", "config_path"]
    return [dict(zip(columns, row)) for row in rows]


def get_latest_scan() -> list[dict]:
    """Fetch results from the most recent scan."""
    rows = execute(
        """SELECT scan_id FROM scan_results
           ORDER BY scanned_at DESC LIMIT 1"""
    )
    if not rows:
        return []
    return get_scan_results(rows[0][0])


def store_scan_run(scan_id: str, workspace_path: str, profile: str, config_hash: str = "") -> None:
    """Store a scan run record (one per scan, not per finding)."""
    from datetime import timezone
    execute(
        "INSERT INTO scan_runs (scan_id, scanned_at, workspace_path, config_hash, profile) VALUES",
        [(scan_id, datetime.now(timezone.utc), workspace_path, config_hash, profile)],
    )


def get_latest_scan_run() -> dict | None:
    """Get metadata for the most recent scan run."""
    rows = execute(
        """SELECT scan_id, scanned_at, workspace_path, config_hash, profile
           FROM scan_runs ORDER BY scanned_at DESC LIMIT 1"""
    )
    if not rows:
        return None
    cols = ["scan_id", "scanned_at", "workspace_path", "config_hash", "profile"]
    return dict(zip(cols, rows[0]))


def list_scans() -> list[dict]:
    """List all scans with summary counts."""
    rows = execute(
        """SELECT scan_id, min(scanned_at) AS scanned_at, any(openclaw_path),
                  any(profile), count() AS check_count,
                  countIf(passed = 0) AS failed_count,
                  countIf(severity = 'CRITICAL' AND passed = 0) AS critical_count,
                  countIf(severity = 'HIGH' AND passed = 0) AS high_count
           FROM scan_results
           GROUP BY scan_id
           ORDER BY scanned_at DESC
           LIMIT 50"""
    )
    columns = ["scan_id", "scanned_at", "openclaw_path", "profile",
               "check_count", "failed_count", "critical_count", "high_count"]
    return [dict(zip(columns, row)) for row in rows]
