"""Attack graph persistence — attack_paths, agent_risk_scores, system_risk."""

import json
from datetime import datetime
from engine.db.client import execute


def upsert_attack_paths(paths: list[dict]):
    if not paths:
        return
    now = datetime.utcnow()
    rows = []
    for p in paths:
        rows.append((
            p["path_id"], p["rule_name"], p["owasp_category"],
            p["agents_involved"], json.dumps(p["path_steps"]),
            p["risk_score"], p["severity"], now, now,
        ))
    execute("INSERT INTO attack_paths VALUES", rows)


def upsert_agent_risk_scores(scores: list[dict]):
    if not scores:
        return
    now = datetime.utcnow()
    rows = []
    for s in scores:
        rows.append((
            s["agent_id"], s["risk_score"], s["severity"],
            s["path_count"], s["top_rule"], now, now,
        ))
    execute("INSERT INTO agent_risk_scores VALUES", rows)


def upsert_system_risk(risk: dict):
    now = datetime.utcnow()
    execute("INSERT INTO system_risk VALUES", [(
        1, risk["risk_score"], risk["severity"],
        risk["critical_paths"], risk["agents_at_risk"],
        risk["learning_agents"], now, now,
    )])


def get_attack_paths(service: str | None = None) -> list[dict]:
    rows = execute(
        """SELECT path_id, rule_name, owasp_category, agents_involved,
                  path_steps, risk_score, severity, computed_at
           FROM attack_paths FINAL
           ORDER BY risk_score DESC"""
    )
    columns = ["path_id", "rule_name", "owasp_category", "agents_involved",
               "path_steps", "risk_score", "severity", "computed_at"]
    results = []
    for row in rows:
        d = dict(zip(columns, row))
        d["path_steps"] = json.loads(d["path_steps"]) if isinstance(d["path_steps"], str) else d["path_steps"]
        results.append(d)

    if service:
        from engine.db.topology import _get_agent_ids_for_service
        allowed = _get_agent_ids_for_service(service)
        results = [r for r in results if set(r["agents_involved"]) & allowed]

    return results


def get_agent_risk_scores(service: str | None = None) -> list[dict]:
    rows = execute(
        """SELECT agent_id, risk_score, severity, path_count, top_rule, computed_at
           FROM agent_risk_scores FINAL
           ORDER BY risk_score DESC"""
    )
    columns = ["agent_id", "risk_score", "severity", "path_count", "top_rule", "computed_at"]
    results = [dict(zip(columns, row)) for row in rows]

    if service:
        from engine.db.topology import _get_agent_ids_for_service
        allowed = _get_agent_ids_for_service(service)
        results = [r for r in results if r["agent_id"] in allowed]

    return results


def get_system_risk() -> dict | None:
    rows = execute(
        """SELECT risk_score, severity, critical_paths, agents_at_risk,
                  learning_agents, computed_at
           FROM system_risk FINAL
           WHERE id = 1"""
    )
    if not rows:
        return None
    columns = ["risk_score", "severity", "critical_paths", "agents_at_risk",
               "learning_agents", "computed_at"]
    return dict(zip(columns, rows[0]))
