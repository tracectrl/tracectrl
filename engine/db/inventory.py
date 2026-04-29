"""Agent inventory upsert/read with cumulative state for ReplacingMergeTree."""

from datetime import datetime
from engine.db.client import execute


def _get_existing_agent(agent_id: str) -> dict | None:
    """Fetch current agent state using FINAL for ReplacingMergeTree correctness."""
    rows = execute(
        """
        SELECT agent_id, name, framework, role, model, tools_observed,
               system_prompt, system_prompt_hash, prompt_template,
               run_count, observation_count, first_seen
        FROM agent_inventory FINAL
        WHERE agent_id = %(id)s
        """,
        {"id": agent_id},
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "agent_id": row[0], "name": row[1], "framework": row[2],
        "role": row[3], "model": row[4], "tools_observed": set(row[5] or []),
        "system_prompt": row[6], "system_prompt_hash": row[7],
        "prompt_template": row[8], "run_count": row[9],
        "observation_count": row[10], "first_seen": row[11],
    }


def update_agent_inventory(spans: list[dict]):
    """Group spans by agent_id and upsert agent_inventory with cumulative state."""
    import logging
    logger = logging.getLogger(__name__)

    agents: dict[str, dict] = {}

    logger.info(f"update_agent_inventory: Processing {len(spans)} total spans")

    for span in spans:
        agent_id = span.get("tc_agent_id")
        if not agent_id:
            continue

        if agent_id not in agents:
            logger.info(f"  Found new agent span: {agent_id}")

        if agent_id not in agents:
            # Start from existing state or fresh
            existing = _get_existing_agent(agent_id)
            if existing:
                agents[agent_id] = existing
                agents[agent_id]["last_seen"] = span["timestamp"]
                agents[agent_id]["_new_obs"] = 0
            else:
                agents[agent_id] = {
                    "agent_id": agent_id,
                    "name": span.get("tc_agent_name", ""),
                    "framework": span.get("tc_agent_framework", ""),
                    "role": span.get("tc_agent_role", ""),
                    "model": span.get("llm_model_name", ""),
                    "tools_observed": set(),
                    "system_prompt": "",
                    "system_prompt_hash": "",
                    "prompt_template": "",
                    "run_count": 0,
                    "observation_count": 0,
                    "first_seen": span["timestamp"],
                    "last_seen": span["timestamp"],
                    "_new_obs": 0,
                }

        agent = agents[agent_id]
        agent["_new_obs"] = agent.get("_new_obs", 0) + 1
        agent["last_seen"] = span["timestamp"]

        if span.get("tool_name"):
            agent["tools_observed"].add(span["tool_name"])
        if span.get("llm_model_name"):
            agent["model"] = span["llm_model_name"]
        if span.get("llm_system"):
            agent["system_prompt"] = span["llm_system"]
            agent["system_prompt_hash"] = span.get("tc_system_prompt_hash", "")

    now = datetime.utcnow()
    logger.info(f"update_agent_inventory: Inserting {len(agents)} agents into inventory")
    for agent in agents.values():
        logger.info(f"  Inserting agent: {agent['agent_id']}")
        tools = list(agent["tools_observed"])
        cumulative_obs = agent["observation_count"] + agent.get("_new_obs", 0)
        run_count = agent["run_count"] + 1
        maturity = "MATURE" if cumulative_obs >= 10 else "LEARNING"

        execute(
            "INSERT INTO agent_inventory VALUES",
            [(
                agent["agent_id"], agent["name"], agent["framework"],
                agent["role"], agent["model"], tools,
                agent["system_prompt"], agent["system_prompt_hash"],
                agent["prompt_template"],
                run_count,
                cumulative_obs,
                maturity,
                agent["first_seen"], agent["last_seen"], now,
            )],
        )
    logger.info("update_agent_inventory: Complete")


def get_all_agents(service: str | None = None) -> list[dict]:
    """Fetch all agents from inventory using FINAL for deduplication."""
    rows = execute(
        """
        SELECT agent_id, name, framework, role, model,
               tools_observed, system_prompt, system_prompt_hash, run_count,
               observation_count, maturity, first_seen, last_seen
        FROM agent_inventory FINAL
        ORDER BY last_seen DESC
        """
    )
    columns = [
        "agent_id", "name", "framework", "role", "model",
        "tools_observed", "system_prompt", "system_prompt_hash", "run_count",
        "observation_count", "maturity", "first_seen", "last_seen",
    ]
    results = [dict(zip(columns, row)) for row in rows]

    # Pull per-tool call counts from topology_tool_edges (single grouped query
    # so we don't fan out N SELECTs across agents).
    tool_rows = execute(
        """
        SELECT agent_id, tool_name, sum(call_count) AS calls
        FROM topology_tool_edges FINAL
        GROUP BY agent_id, tool_name
        """
    )
    counts_by_agent: dict[str, dict[str, int]] = {}
    totals_by_agent: dict[str, int] = {}
    for agent_id, tool_name, calls in tool_rows:
        counts_by_agent.setdefault(agent_id, {})[tool_name] = int(calls or 0)
        totals_by_agent[agent_id] = totals_by_agent.get(agent_id, 0) + int(calls or 0)
    for r in results:
        r["tool_call_counts"] = counts_by_agent.get(r["agent_id"], {})
        r["total_tool_calls"] = totals_by_agent.get(r["agent_id"], 0)

    if service:
        svc_rows = execute(
            """
            SELECT DISTINCT
                SpanAttributes['tracectrl.agent.id'] AS tc_id,
                SpanAttributes['agno.agent.id'] AS agno_id,
                SpanAttributes['agent.name'] AS agent_name
            FROM otel_traces
            WHERE ServiceName = %(service)s
              AND SpanAttributes['openinference.span.kind'] = 'AGENT'
            """,
            {"service": service},
        )
        allowed_ids = set()
        for r in svc_rows:
            for val in r:
                if val:
                    allowed_ids.add(val)
        results = [a for a in results if a["agent_id"] in allowed_ids]

    return results


def get_tools_for_agent(agent_id: str) -> list[dict]:
    rows = execute(
        """
        SELECT tool_name, tool_category, call_count, error_count,
               first_seen, last_seen
        FROM topology_tool_edges FINAL
        WHERE agent_id = %(id)s
        ORDER BY call_count DESC
        """,
        {"id": agent_id},
    )
    columns = [
        "tool_name", "tool_category", "call_count", "error_count",
        "first_seen", "last_seen",
    ]
    return [dict(zip(columns, row)) for row in rows]


def get_agent_by_id(agent_id: str) -> dict | None:
    """Fetch a single agent by ID using FINAL."""
    rows = execute(
        """
        SELECT agent_id, name, framework, role, model,
               tools_observed, system_prompt_hash, run_count,
               observation_count, maturity, first_seen, last_seen
        FROM agent_inventory FINAL
        WHERE agent_id = %(id)s
        """,
        {"id": agent_id},
    )
    if not rows:
        return None
    columns = [
        "agent_id", "name", "framework", "role", "model",
        "tools_observed", "system_prompt_hash", "run_count",
        "observation_count", "maturity", "first_seen", "last_seen",
    ]
    return dict(zip(columns, rows[0]))
