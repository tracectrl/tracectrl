"""Merge static scan topology with dynamic runtime topology."""
import logging
from datetime import datetime
from engine.db.client import execute

logger = logging.getLogger(__name__)


def merge_static_topology(scan_topology: dict) -> None:
    """Merge nodes and edges from a static scan into the runtime topology tables.

    Static nodes get source='static'. If a node already exists from runtime
    (source='dynamic'), it becomes 'merged'.
    """
    now = datetime.utcnow()

    for node in scan_topology.get("nodes", []):
        node_id = node["id"]
        node_type = node.get("type", "")
        try:
            # Check if node exists in agent_inventory
            existing = execute(
                "SELECT agent_id FROM agent_inventory FINAL WHERE agent_id = %(id)s",
                {"id": node_id},
            )
            if existing:
                # Node exists from runtime — update timestamp to mark it as merged
                execute(
                    "ALTER TABLE agent_inventory UPDATE "
                    "updated_at = %(now)s "
                    "WHERE agent_id = %(id)s",
                    {"id": node_id, "now": now},
                )
            else:
                # Static-only node — add to inventory with observation_count=0
                if node_type in ("AGENT", "INGRESS"):
                    execute(
                        "INSERT INTO agent_inventory VALUES",
                        [(
                            node_id, node.get("label", node_id),
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
        except Exception:
            logger.exception("Failed to merge node %s", node_id)

    # Insert edges, including TOOL edges into topology_tool_edges
    for edge in scan_topology.get("edges", []):
        try:
            source = edge["source"]
            target = edge["target"]
            edge_type = edge.get("type", "")

            if edge_type == "TOOL":
                execute(
                    "INSERT INTO topology_tool_edges VALUES",
                    [(source, target, "static", now)],
                )
            else:
                execute(
                    "INSERT INTO topology_edges VALUES",
                    [(source, target, edge_type, "static", now)],
                )
        except Exception:
            logger.exception(
                "Failed to merge edge %s -> %s", edge.get("source"), edge.get("target")
            )
