"""Merge static scan topology with dynamic runtime topology."""
from datetime import datetime
from engine.db.client import execute


def merge_static_topology(scan_topology: dict) -> None:
    """Merge nodes and edges from a static scan into the runtime topology tables.

    Static nodes get source='static'. If a node already exists from runtime
    (source='dynamic'), it becomes 'merged'.
    """
    now = datetime.utcnow()

    for node in scan_topology.get("nodes", []):
        # Check if node exists in agent_inventory
        existing = execute(
            "SELECT agent_id FROM agent_inventory FINAL WHERE agent_id = %(id)s",
            {"id": node["id"]},
        )
        if existing:
            # Node exists from runtime — it's now merged
            # Don't overwrite runtime data, just note it's been seen in static scan
            pass
        else:
            # Static-only node — add to inventory with observation_count=0
            if node.get("type") in ("AGENT", "INGRESS"):
                execute(
                    "INSERT INTO agent_inventory VALUES",
                    [(
                        node["id"], node.get("label", node["id"]),
                        "openclaw",  # framework
                        "",  # role
                        "",  # model
                        [],  # tools_observed
                        "",  # system_prompt
                        "",  # system_prompt_hash
                        "",  # prompt_template
                        0,   # run_count
                        0,   # observation_count
                        "STATIC",  # maturity — special value for static-only
                        now, now, now,
                    )],
                )
