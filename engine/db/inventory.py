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
    agents: dict[str, dict] = {}

    for span in spans:
        agent_id = span.get("tc_agent_id")
        if not agent_id:
            continue

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
    for agent in agents.values():
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


def get_all_agents() -> list[dict]:
    """Fetch all agents from inventory using FINAL for deduplication."""
    rows = execute(
        """
        SELECT agent_id, name, framework, role, model,
               tools_observed, system_prompt_hash, run_count,
               observation_count, maturity, first_seen, last_seen
        FROM agent_inventory FINAL
        ORDER BY last_seen DESC
        """
    )
    columns = [
        "agent_id", "name", "framework", "role", "model",
        "tools_observed", "system_prompt_hash", "run_count",
        "observation_count", "maturity", "first_seen", "last_seen",
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
