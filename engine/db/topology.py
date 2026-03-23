"""Topology edge upsert/read with cumulative state for ReplacingMergeTree."""

import hashlib
import json
from datetime import datetime
from engine.db.client import execute


def _get_existing_agent_edge(edge_id: str) -> dict | None:
    """Fetch current agent edge state using FINAL."""
    rows = execute(
        """
        SELECT edge_id, observation_count, first_seen
        FROM topology_agent_edges FINAL
        WHERE edge_id = %(id)s
        """,
        {"id": edge_id},
    )
    if not rows:
        return None
    return {
        "observation_count": rows[0][1],
        "first_seen": rows[0][2],
    }


def _get_existing_tool_edge(edge_id: str) -> dict | None:
    """Fetch current tool edge state using FINAL."""
    rows = execute(
        """
        SELECT edge_id, call_count, call_contexts, error_count, first_seen
        FROM topology_tool_edges FINAL
        WHERE edge_id = %(id)s
        """,
        {"id": edge_id},
    )
    if not rows:
        return None
    ctx = rows[0][2]
    if isinstance(ctx, str):
        try:
            ctx = json.loads(ctx)
        except (json.JSONDecodeError, TypeError):
            ctx = {"user": 0, "agent": 0, "external": 0, "memory": 0}
    return {
        "call_count": rows[0][1],
        "call_contexts": ctx or {"user": 0, "agent": 0, "external": 0, "memory": 0},
        "error_count": rows[0][3],
        "first_seen": rows[0][4],
    }


def update_topology(spans: list[dict]):
    """Build agent->agent and agent->tool edges from spans."""
    agent_edges: dict[str, dict] = {}
    tool_edges: dict[str, dict] = {}
    now = datetime.utcnow()

    # --- Pre-processing: resolve owning agent via parent_span_id ---
    # Key by (trace_id, span_id) to avoid cross-trace collisions.
    # Build initial lookup from AGENT spans, then iteratively propagate
    # through intermediate spans (e.g. LLM spans between AGENT and TOOL).
    span_key_to_agent: dict[tuple[str, str], str] = {}
    span_key_to_parent: dict[tuple[str, str], tuple[str, str]] = {}

    for span in spans:
        tid = span.get("trace_id", "")
        sid = span.get("span_id", "")
        psid = span.get("parent_span_id", "")
        if tid and sid:
            if span.get("oi_span_kind") == "AGENT" and span.get("tc_agent_id"):
                span_key_to_agent[(tid, sid)] = span["tc_agent_id"]
            if psid:
                span_key_to_parent[(tid, sid)] = (tid, psid)

    # Iteratively propagate agent ownership through the span tree
    # (handles multi-level: AGENT → LLM → TOOL)
    changed = True
    while changed:
        changed = False
        for key, parent_key in span_key_to_parent.items():
            if key not in span_key_to_agent and parent_key in span_key_to_agent:
                span_key_to_agent[key] = span_key_to_agent[parent_key]
                changed = True

    # Apply resolved agent IDs to spans that lack them
    for span in spans:
        if not span.get("tc_agent_id"):
            key = (span.get("trace_id", ""), span.get("span_id", ""))
            if key in span_key_to_agent:
                span["tc_agent_id"] = span_key_to_agent[key]

    for span in spans:
        agent_id = span.get("tc_agent_id", "")
        caller_id = span.get("tc_caller_agent_id", "")
        parent_sid = span.get("parent_span_id", "")

        # Agent->Agent edges (explicit caller_id or team→member via parent)
        if agent_id and caller_id:
            edge_key = f"{caller_id}:{agent_id}"
            edge_id = hashlib.md5(edge_key.encode()).hexdigest()[:16]
            if edge_id not in agent_edges:
                existing = _get_existing_agent_edge(edge_id)
                if existing:
                    agent_edges[edge_id] = {
                        "edge_id": edge_id,
                        "caller_agent_id": caller_id,
                        "callee_agent_id": agent_id,
                        "channel": "function_call",
                        "observation_count": existing["observation_count"],
                        "first_seen": existing["first_seen"],
                        "last_seen": span["timestamp"],
                    }
                else:
                    agent_edges[edge_id] = {
                        "edge_id": edge_id,
                        "caller_agent_id": caller_id,
                        "callee_agent_id": agent_id,
                        "channel": "function_call",
                        "observation_count": 0,
                        "first_seen": span["timestamp"],
                        "last_seen": span["timestamp"],
                    }
            agent_edges[edge_id]["observation_count"] += 1
            agent_edges[edge_id]["last_seen"] = span["timestamp"]

        # Team→member edges: AGENT span whose parent is also an AGENT span
        parent_key = (span.get("trace_id", ""), parent_sid) if parent_sid else None
        if (
            span.get("oi_span_kind") == "AGENT"
            and agent_id
            and not caller_id
            and parent_key
            and parent_key in span_key_to_agent
        ):
            parent_agent_id = span_key_to_agent[parent_key]
            if parent_agent_id != agent_id:
                edge_key = f"{parent_agent_id}:{agent_id}"
                edge_id = hashlib.md5(edge_key.encode()).hexdigest()[:16]
                if edge_id not in agent_edges:
                    existing = _get_existing_agent_edge(edge_id)
                    if existing:
                        agent_edges[edge_id] = {
                            "edge_id": edge_id,
                            "caller_agent_id": parent_agent_id,
                            "callee_agent_id": agent_id,
                            "channel": "team_member",
                            "observation_count": existing["observation_count"],
                            "first_seen": existing["first_seen"],
                            "last_seen": span["timestamp"],
                        }
                    else:
                        agent_edges[edge_id] = {
                            "edge_id": edge_id,
                            "caller_agent_id": parent_agent_id,
                            "callee_agent_id": agent_id,
                            "channel": "team_member",
                            "observation_count": 0,
                            "first_seen": span["timestamp"],
                            "last_seen": span["timestamp"],
                        }
                agent_edges[edge_id]["observation_count"] += 1
                agent_edges[edge_id]["last_seen"] = span["timestamp"]

        # Agent->Tool edges
        tool_name = span.get("tool_name", "")
        if agent_id and tool_name:
            edge_key = f"{agent_id}:{tool_name}"
            edge_id = hashlib.md5(edge_key.encode()).hexdigest()[:16]
            if edge_id not in tool_edges:
                existing = _get_existing_tool_edge(edge_id)
                if existing:
                    tool_edges[edge_id] = {
                        "edge_id": edge_id,
                        "agent_id": agent_id,
                        "tool_name": tool_name,
                        "tool_category": span.get("tc_tool_category", "internal_api"),
                        "call_count": existing["call_count"],
                        "call_contexts": existing["call_contexts"],
                        "error_count": existing["error_count"],
                        "first_seen": existing["first_seen"],
                        "last_seen": span["timestamp"],
                    }
                else:
                    tool_edges[edge_id] = {
                        "edge_id": edge_id,
                        "agent_id": agent_id,
                        "tool_name": tool_name,
                        "tool_category": span.get("tc_tool_category", "internal_api"),
                        "call_count": 0,
                        "call_contexts": {"user": 0, "agent": 0, "external": 0, "memory": 0},
                        "error_count": 0,
                        "first_seen": span["timestamp"],
                        "last_seen": span["timestamp"],
                    }
            edge = tool_edges[edge_id]
            edge["call_count"] += 1
            edge["last_seen"] = span["timestamp"]
            source = span.get("tc_input_source") or "user"
            if source in edge["call_contexts"]:
                edge["call_contexts"][source] += 1
            if span.get("status_code") == "ERROR":
                edge["error_count"] += 1

    # Upsert agent edges (cumulative counts)
    for edge in agent_edges.values():
        obs = edge["observation_count"]
        confidence = "HIGH" if obs >= 20 else ("MEDIUM" if obs >= 5 else "LOW")
        execute(
            "INSERT INTO topology_agent_edges VALUES",
            [(
                edge["edge_id"], edge["caller_agent_id"], edge["callee_agent_id"],
                edge["channel"], obs, confidence,
                edge["first_seen"], edge["last_seen"], now,
            )],
        )

    # Upsert tool edges (cumulative counts)
    for edge in tool_edges.values():
        execute(
            "INSERT INTO topology_tool_edges VALUES",
            [(
                edge["edge_id"], edge["agent_id"], edge["tool_name"],
                edge["tool_category"], edge["call_count"],
                json.dumps(edge["call_contexts"]),
                "[]",  # last_parameters placeholder
                edge["error_count"],
                edge["first_seen"], edge["last_seen"], now,
            )],
        )


def _get_agent_ids_for_service(service: str) -> set[str]:
    """Return the set of agent_ids that appear in spans for a given service.

    Checks tracectrl.agent.id first, falls back to agno.agent.id,
    then derives an ID from agent.name (lowercase, spaces to hyphens).
    """
    rows = execute(
        """SELECT DISTINCT
               SpanAttributes['tracectrl.agent.id'] AS tc_id,
               SpanAttributes['agno.agent.id'] AS agno_id,
               SpanAttributes['agent.name'] AS agent_name,
               SpanName
           FROM otel_traces
           WHERE ServiceName = %(service)s
             AND SpanAttributes['openinference.span.kind'] = 'AGENT'""",
        {"service": service},
    )
    ids = set()
    for row in rows:
        tc_id, agno_id, agent_name, span_name = row[0], row[1], row[2], row[3]
        agent_id = tc_id or agno_id
        if not agent_id:
            name = agent_name
            if not name and span_name:
                if span_name.startswith("invoke_agent "):
                    name = span_name.replace("invoke_agent ", "")
                elif span_name.endswith(".run"):
                    name = span_name.replace(".run", "").replace("_", " ")
                else:
                    name = span_name
            if name:
                agent_id = name.lower().replace(" ", "-")
        if agent_id:
            ids.add(agent_id)
    return ids


def get_topology_graph(service: str | None = None) -> dict:
    """Build the full topology graph for the API.

    When *service* is provided, only agents (and their edges) that appear
    in spans for that ServiceName are included.
    """
    allowed_ids: set[str] | None = None
    if service:
        allowed_ids = _get_agent_ids_for_service(service)

    agents = execute(
        "SELECT agent_id, name, framework, role, model, tools_observed, maturity FROM agent_inventory FINAL"
    )
    agent_edges = execute(
        "SELECT edge_id, caller_agent_id, callee_agent_id, channel, observation_count, confidence FROM topology_agent_edges FINAL"
    )
    tool_edges = execute(
        "SELECT edge_id, agent_id, tool_name, tool_category, call_count FROM topology_tool_edges FINAL"
    )

    nodes = []
    edges = []
    tool_nodes_seen = set()

    # Agent nodes
    for row in agents:
        if allowed_ids is not None and row[0] not in allowed_ids:
            continue
        nodes.append({
            "id": row[0],
            "type": "agent",
            "label": row[1] or row[0],
            "metadata": {
                "framework": row[2],
                "role": row[3],
                "model": row[4],
                "tools_observed": row[5],
                "maturity": row[6],
            },
        })

    # Agent->Agent edges
    for row in agent_edges:
        if allowed_ids is not None and (row[1] not in allowed_ids or row[2] not in allowed_ids):
            continue
        edges.append({
            "id": row[0],
            "source": row[1],
            "target": row[2],
            "type": "agent_to_agent",
            "channel": row[3],
            "observation_count": row[4],
            "confidence": row[5],
        })

    # Tool nodes + Agent->Tool edges
    for row in tool_edges:
        if allowed_ids is not None and row[1] not in allowed_ids:
            continue
        tool_id = f"tool:{row[2]}"
        if tool_id not in tool_nodes_seen:
            tool_nodes_seen.add(tool_id)
            nodes.append({
                "id": tool_id,
                "type": "tool",
                "label": row[2],
                "metadata": {"category": row[3]},
            })
        edges.append({
            "id": row[0],
            "source": row[1],
            "target": tool_id,
            "type": "agent_to_tool",
            "call_count": row[4],
            "tool_category": row[3],
        })

    return {"nodes": nodes, "edges": edges}
