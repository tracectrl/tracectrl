"""Scan result storage and retrieval."""
import uuid
from datetime import datetime
from engine.db.client import execute


def store_scan_results(results: list[dict], openclaw_path: str, profile: str) -> str:
    """Store scan results in ClickHouse. Returns the scan_id."""
    scan_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow()

    for r in results:
        execute(
            "INSERT INTO scan_results VALUES",
            [(
                scan_id, now, openclaw_path, profile,
                r["check_id"], r["section"], r["title"],
                r["severity"], 1 if r["passed"] else 0,
                r.get("finding", ""), r.get("remediation", ""),
                r.get("config_path", ""),
            )],
        )
    return scan_id


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
