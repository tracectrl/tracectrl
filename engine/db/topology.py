"""Topology edge upsert/read with cumulative state for ReplacingMergeTree."""

import hashlib
import json
import re
from datetime import datetime
from engine.db.client import execute

# Tool filtering configuration
# Tools matching these patterns will be excluded from topology visualization
EXCLUDED_TOOL_PATTERNS = [
    r".*_session_context$",  # read_session_context, update_session_context, etc.
    r"^read_.*_context$",     # read_*_context
    r"^update_.*_context$",   # update_*_context
    r"^get_.*_context$",      # get_*_context
    r"^set_.*_context$",      # set_*_context
]


def _should_exclude_tool(tool_name: str) -> bool:
    """Check if a tool should be excluded from topology based on configured patterns."""
    for pattern in EXCLUDED_TOOL_PATTERNS:
        if re.match(pattern, tool_name, re.IGNORECASE):
            return True
    return False


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

    # --- Step 1: Identify traces with external ingress origin ---
    external_traces: set[str] = set()
    EXTERNAL_TRIGGERS = {
        "upload", "email", "webhook", "manual",
        # OpenClaw channels — gateway-fronted ingress sources
        "webchat", "telegram", "slack", "discord", "sms", "whatsapp", "api",
    }

    for span in spans:
        if span.get("tc_ingress"):  # truthy: bool True or non-empty string
            trigger_type = span.get("tc_trigger_type", "")
            if trigger_type in EXTERNAL_TRIGGERS:
                external_traces.add(span.get("trace_id", ""))

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
        # Skip delegation wrappers (agent-as-tool pattern) — they create agent->agent edges instead
        tool_name = span.get("tool_name", "")
        tool_category = span.get("tc_tool_category", "internal_api")

        # Skip excluded tools (e.g., session context functions)
        if agent_id and tool_name and tool_category != "agent_delegation" and not _should_exclude_tool(tool_name):
            edge_key = f"{agent_id}:{tool_name}"
            edge_id = hashlib.md5(edge_key.encode()).hexdigest()[:16]
            if edge_id not in tool_edges:
                existing = _get_existing_tool_edge(edge_id)
                if existing:
                    tool_edges[edge_id] = {
                        "edge_id": edge_id,
                        "agent_id": agent_id,
                        "tool_name": tool_name,
                        "tool_category": tool_category,
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
                        "tool_category": tool_category,
                        "call_count": 0,
                        "call_contexts": {"user": 0, "agent": 0, "external": 0, "memory": 0},
                        "error_count": 0,
                        "first_seen": span["timestamp"],
                        "last_seen": span["timestamp"],
                    }
            edge = tool_edges[edge_id]
            edge["call_count"] += 1
            edge["last_seen"] = span["timestamp"]

            # Determine input source: if trace has external ingress origin,
            # mark as "external" regardless of immediate tc_input_source
            trace_id = span.get("trace_id", "")
            if trace_id in external_traces:
                source = "external"
            else:
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
               SpanName,
               SpanAttributes['channel'] AS oc_channel
           FROM otel_traces
           WHERE ServiceName = %(service)s
             AND (SpanAttributes['openinference.span.kind'] = 'AGENT'
                  OR SpanName LIKE 'openclaw.%%'
                  OR (SpanAttributes['openinference.span.kind'] = 'CHAIN'
                      AND position(lower(SpanName), '_agent') > 0
                      AND SpanName LIKE '%%.execute'))""",
        {"service": service},
    )
    ids = set()
    for row in rows:
        tc_id, agno_id, agent_name, span_name = row[0], row[1], row[2], row[3]
        oc_channel = row[4] if len(row) > 4 else ""
        agent_id = tc_id or agno_id
        if not agent_id:
            if span_name.startswith("openclaw."):
                # All openclaw.* spans roll up to a single canonical gateway agent
                # since OpenClaw doesn't propagate parent context across spans.
                name = "openclaw-gateway"
            elif not agent_name and span_name:
                if span_name.startswith("invoke_agent "):
                    name = span_name.replace("invoke_agent ", "")
                elif span_name.endswith(".run"):
                    name = span_name.replace(".run", "").replace("_", " ")
                elif span_name.endswith(".execute") and "_agent" in span_name.lower():
                    name = span_name.replace(".execute", "").replace("_", " ")
                else:
                    name = ""  # Don't create agent IDs from unrecognized span names
            else:
                name = agent_name
            if name:
                agent_id = name.lower().replace(" ", "-")
        if agent_id:
            ids.add(agent_id)
    return ids


def _get_child_agent_id(ingress_span_id: str) -> str | None:
    """Find the first child AGENT span of an ingress span."""
    rows = execute(
        """
        SELECT SpanAttributes['tracectrl.agent.id'], SpanAttributes['agno.agent.id']
        FROM otel_traces
        WHERE ParentSpanId = %(span_id)s
          AND SpanAttributes['openinference.span.kind'] = 'AGENT'
        LIMIT 1
        """,
        {"span_id": ingress_span_id}
    )
    if rows and (rows[0][0] or rows[0][1]):
        return rows[0][0] or rows[0][1]
    return None


def _get_ingress_triggers(service: str | None = None) -> list[dict]:
    """Get ingress triggers (root spans marked as ingress points)."""
    import logging
    logger = logging.getLogger(__name__)

    base_select = """
        SELECT DISTINCT
            if(SpanAttributes['tracectrl.trigger_type'] != '',
               SpanAttributes['tracectrl.trigger_type'],
               JSONExtractString(SpanAttributes['metadata'], 'tracectrl.trigger_type')
            ) AS trigger_type,
            SpanAttributes['tracectrl.agent.id'] AS agent_id,
            SpanAttributes['agno.agent.id'] AS agno_agent_id,
            SpanAttributes['agent.name'] AS agent_name,
            SpanName,
            SpanId,
            SpanAttributes['openclaw.channel'] AS oc_channel
    """
    base_where = """
        WHERE (SpanAttributes['tracectrl.ingress'] = 'True'
               OR SpanAttributes['tracectrl.ingress'] = 'true'
               OR JSONExtractString(SpanAttributes['metadata'], 'tracectrl.ingress') = 'true'
               OR (ParentSpanId = ''
                   AND (SpanAttributes['openinference.span.kind'] = 'AGENT'
                        OR SpanName LIKE '%%.execute'
                        OR SpanName LIKE 'invoke_agent %%'))
               OR (SpanName IN ('openclaw.run', 'openclaw.message.processed')
                   AND SpanAttributes['openclaw.channel'] != ''))
    """
    if service:
        rows = execute(
            base_select + " FROM otel_traces " + base_where + " AND ServiceName = %(service)s",
            {"service": service},
        )
    else:
        rows = execute(base_select + " FROM otel_traces " + base_where)

    logger.critical(f"[_get_ingress_triggers] ===== Found {len(rows)} ingress spans =====")

    triggers = []
    for row in rows:
        trigger_type = row[0]  # May be empty
        first_agent_id = row[1] or row[2]  # agent_id or agno_agent_id
        agent_name = row[3]
        span_name = row[4]
        span_id = row[5]
        oc_channel = row[6] if len(row) > 6 else ""

        logger.info(f"[_get_ingress_triggers] Processing: trigger_type={trigger_type}, span_name={span_name}, agent_id={first_agent_id}, oc_channel={oc_channel}")

        # OpenClaw: channel is the trigger, gateway is the agent.
        # Filter out internal pseudo-channels (heartbeat, cron, tick) — these are
        # liveness/scheduled internals, not real external ingress.
        OC_INTERNAL_CHANNELS = {"heartbeat", "cron", "tick", "internal"}
        if (
            span_name in ("openclaw.run", "openclaw.message.processed")
            and oc_channel
            and oc_channel not in OC_INTERNAL_CHANNELS
        ):
            trigger_type = oc_channel
            first_agent_id = "openclaw-gateway"
        elif span_name in ("openclaw.run", "openclaw.message.processed") and oc_channel in OC_INTERNAL_CHANNELS:
            # Skip internal channels entirely
            continue

        # Fallback inference: if no trigger_type attribute, infer from span name
        if not trigger_type and span_name:
            span_lower = span_name.lower()
            if any(p in span_lower for p in ["email", "mail", "imap", "smtp", "inbox"]):
                trigger_type = "email"
            elif any(p in span_lower for p in ["upload", "file_upload", "document_upload"]):
                trigger_type = "upload"
            elif any(p in span_lower for p in ["webhook", "http_trigger", "api_trigger"]):
                trigger_type = "webhook"
            elif any(p in span_lower for p in ["schedule", "cron", "timer", "periodic"]):
                trigger_type = "scheduled"
            elif any(p in span_lower for p in ["manual", "user_request", "direct"]):
                trigger_type = "manual"
            else:
                trigger_type = "external"  # Default fallback
        elif not trigger_type:
            trigger_type = "external"

        # Derive agent ID if not explicitly set
        if not first_agent_id:
            # For ingress spans, try to find child agent
            if span_name and span_name.startswith("ingress."):
                first_agent_id = _get_child_agent_id(span_id)
                if not first_agent_id:
                    continue  # Skip this trigger - no child agent found

            # For other spans, derive from span name
            elif span_name.startswith("invoke_agent "):
                name = span_name.replace("invoke_agent ", "")
                first_agent_id = name.lower().replace(" ", "-")
            elif span_name.endswith(".run"):
                name = span_name.replace(".run", "").replace("_", " ")
                first_agent_id = name.lower().replace(" ", "-")
            elif span_name.endswith(".execute"):
                name = span_name.replace(".execute", "").replace("_", " ")
                first_agent_id = name.lower().replace(" ", "-")
            else:
                name = agent_name or span_name
                if name:
                    first_agent_id = name.lower().replace(" ", "-")

        logger.info(f"[_get_ingress_triggers] After derivation: first_agent_id={first_agent_id}, trigger_type={trigger_type}")

        if first_agent_id:
            # Only include explicitly marked ingress triggers
            # Filter out "external" fallback for root spans that aren't real entry points
            if trigger_type != "external":
                logger.info(f"[_get_ingress_triggers] ✓ Adding trigger: {trigger_type} -> {first_agent_id}")
                triggers.append({
                    "trigger_type": trigger_type,
                    "target_agent_id": first_agent_id,
                })
            else:
                logger.info(f"[_get_ingress_triggers] ✗ Skipping 'external' trigger for {first_agent_id}")
        else:
            logger.info("[_get_ingress_triggers] ✗ Skipping - no agent_id found")

    # Deduplicate by (trigger_type, target_agent_id)
    seen = set()
    unique_triggers = []
    for t in triggers:
        key = (t["trigger_type"], t["target_agent_id"])
        if key not in seen:
            seen.add(key)
            unique_triggers.append(t)

    logger.info(f"[_get_ingress_triggers] Returning {len(unique_triggers)} unique triggers: {unique_triggers}")
    return unique_triggers


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
    ingress_nodes_seen = set()

    # Ingress nodes (entry points / triggers)
    ingress_triggers = _get_ingress_triggers(service)
    for trigger in ingress_triggers:
        trigger_type = trigger["trigger_type"]
        target_agent = trigger["target_agent_id"]

        # Create ingress node
        ingress_id = f"ingress:{trigger_type}"
        if ingress_id not in ingress_nodes_seen:
            ingress_nodes_seen.add(ingress_id)
            # Format label: capitalize first letter of each word
            label = trigger_type.replace("_", " ").title()
            if trigger_type == "external":
                label = "External Trigger"
            nodes.append({
                "id": ingress_id,
                "type": "ingress",
                "label": label,
                "metadata": {"trigger_type": trigger_type},
            })

        # Create edge from ingress to first agent
        if target_agent:
            # Skip if agent is filtered out
            if allowed_ids is not None and target_agent not in allowed_ids:
                continue
            edge_id = hashlib.md5(f"{ingress_id}:{target_agent}".encode()).hexdigest()[:16]
            edges.append({
                "id": edge_id,
                "source": ingress_id,
                "target": target_agent,
                "type": "ingress_to_agent",
                "trigger_type": trigger_type,
            })

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

    # Agent->Agent edges (delegation + return edges)
    for row in agent_edges:
        if allowed_ids is not None and (row[1] not in allowed_ids or row[2] not in allowed_ids):
            continue

        # Forward edge (delegation): caller -> callee
        edge_id = row[0]
        caller_id = row[1]
        callee_id = row[2]
        channel = row[3]
        obs_count = row[4]
        confidence = row[5]

        edges.append({
            "id": edge_id,
            "source": caller_id,
            "target": callee_id,
            "type": "agent_to_agent",
            "channel": channel,
            "observation_count": obs_count,
            "confidence": confidence,
            "direction": "delegation",  # Mark as delegation edge
        })

        # Return edge (data flow): callee -> caller
        # This shows where results/data flow back to
        return_edge_id = f"{edge_id}_return"
        edges.append({
            "id": return_edge_id,
            "source": callee_id,
            "target": caller_id,
            "type": "agent_return",
            "channel": "returns_to",
            "observation_count": obs_count,
            "confidence": confidence,
            "direction": "return",  # Mark as return/data flow edge
        })

    # Tool nodes + Agent->Tool edges (forward and return)
    for row in tool_edges:
        if allowed_ids is not None and row[1] not in allowed_ids:
            continue
        tool_name = row[2]
        # Skip excluded tools
        if _should_exclude_tool(tool_name):
            continue
        tool_id = f"tool:{tool_name}"
        agent_id = row[1]
        edge_id = row[0]

        if tool_id not in tool_nodes_seen:
            tool_nodes_seen.add(tool_id)
            nodes.append({
                "id": tool_id,
                "type": "tool",
                "label": tool_name,
                "metadata": {"category": row[3]},
            })

        # Forward edge: Agent → Tool (uses/calls)
        edges.append({
            "id": edge_id,
            "source": agent_id,
            "target": tool_id,
            "type": "agent_to_tool",
            "call_count": row[4],
            "tool_category": row[3],
            "direction": "delegation",
        })

        # Return edge: Tool → Agent (returns data)
        return_edge_id = f"{edge_id}_return"
        edges.append({
            "id": return_edge_id,
            "source": tool_id,
            "target": agent_id,
            "type": "tool_return",
            "call_count": row[4],
            "tool_category": row[3],
            "direction": "return",
        })

    return {"nodes": nodes, "edges": edges}
