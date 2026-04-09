"""Static topology builder for OpenClaw configurations.

Parses an OpenClaw config dict and produces a TopologyGraph representing
all nodes (ingress channels, agents, tools, LLM providers, etc.) and the
edges between them.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .models import Edge, EdgeType, Node, NodeType, TopologyGraph


# Channels that accept messages from the public internet.
_INTERNET_CHANNELS = {"whatsapp", "telegram", "discord", "slack", "web", "api"}

# Keys whose presence (with a truthy value) signals a channel is configured.
_CHANNEL_CONFIG_SIGNALS = {"token", "bot_token", "api_key", "webhook_url", "app_id"}


def _edge_id(source: str, target: str, edge_type: str) -> str:
    """Deterministic short hash for an edge."""
    return hashlib.md5(f"{source}:{target}:{edge_type}".encode()).hexdigest()[:12]


def _is_channel_enabled(channel_cfg: Any) -> bool:
    """Return True when a channel block looks enabled."""
    if not isinstance(channel_cfg, dict):
        return False
    if channel_cfg.get("enabled") is True:
        return True
    # If there is no explicit `enabled` key, infer from presence of credentials.
    return any(channel_cfg.get(k) for k in _CHANNEL_CONFIG_SIGNALS)


# ----------------------------------------------------------------------- #
# Builder
# ----------------------------------------------------------------------- #

def build(
    config: dict[str, Any],
    openclaw_root: Path,
    agent_ids: list[str],
) -> TopologyGraph:
    """Build a :class:`TopologyGraph` from an OpenClaw configuration dict.

    Parameters
    ----------
    config:
        Parsed OpenClaw YAML configuration (the full dict).
    openclaw_root:
        Filesystem path to the OpenClaw project root — used to discover
        extension directories.
    agent_ids:
        Pre-resolved list of agent identifiers.  When empty the builder
        will synthesize a ``default`` agent if ``agents.defaults`` exists.
    """

    graph = TopologyGraph()

    # -- 1. Ingress nodes ------------------------------------------------ #
    ingress_ids: list[str] = []
    channels: dict[str, Any] = config.get("channels", {})
    for ch_name, ch_cfg in channels.items():
        if _is_channel_enabled(ch_cfg):
            node_id = f"ingress:{ch_name}"
            graph.nodes.append(
                Node(
                    id=node_id,
                    type=NodeType.INGRESS,
                    label=ch_name.title(),
                    properties={"channel": ch_name},
                )
            )
            ingress_ids.append(node_id)

    # -- 2. Agent nodes -------------------------------------------------- #
    resolved_agent_ids: list[str] = list(agent_ids)
    agents_cfg: dict[str, Any] = config.get("agents", {})

    if not resolved_agent_ids:
        agent_list = agents_cfg.get("list", [])
        if agent_list:
            for entry in agent_list:
                if isinstance(entry, dict):
                    aid = entry.get("id") or entry.get("name", "agent")
                    resolved_agent_ids.append(str(aid))
                else:
                    resolved_agent_ids.append(str(entry))
        elif agents_cfg.get("defaults"):
            resolved_agent_ids.append("default")

    for aid in resolved_agent_ids:
        graph.nodes.append(
            Node(
                id=f"agent:{aid}",
                type=NodeType.AGENT,
                label=aid,
            )
        )

    # -- 3. Ingress → Agent edges (routes_to) --------------------------- #
    for ing_id in ingress_ids:
        for aid in resolved_agent_ids:
            etype = EdgeType.ROUTES_TO
            target = f"agent:{aid}"
            graph.edges.append(
                Edge(
                    id=_edge_id(ing_id, target, etype.value),
                    source=ing_id,
                    target=target,
                    type=etype,
                )
            )

    # -- 4. LLM Provider nodes ------------------------------------------ #
    provider_ids: list[str] = []
    models_cfg: dict[str, Any] = config.get("models", {})
    providers: dict[str, Any] = models_cfg.get("providers", {})
    for prov_name in providers:
        node_id = f"llm:{prov_name}"
        graph.nodes.append(
            Node(
                id=node_id,
                type=NodeType.LLM_PROVIDER,
                label=prov_name,
                properties=providers[prov_name] if isinstance(providers[prov_name], dict) else {},
            )
        )
        provider_ids.append(node_id)

    # -- 5. Agent → LLM Provider edges (calls) -------------------------- #
    for aid in resolved_agent_ids:
        for prov_id in provider_ids:
            etype = EdgeType.CALLS
            source = f"agent:{aid}"
            graph.edges.append(
                Edge(
                    id=_edge_id(source, prov_id, etype.value),
                    source=source,
                    target=prov_id,
                    type=etype,
                )
            )

    # -- 6. Tool nodes --------------------------------------------------- #
    tool_ids: list[str] = []
    seen_tools: set[str] = set()

    def _collect_tools(tools_list: list[Any]) -> None:
        for t in tools_list:
            name = t if isinstance(t, str) else (t.get("name") if isinstance(t, dict) else str(t))
            if name and name not in seen_tools:
                seen_tools.add(name)
                node_id = f"tool:{name}"
                graph.nodes.append(
                    Node(id=node_id, type=NodeType.TOOL, label=name)
                )
                tool_ids.append(node_id)

    # From agents.defaults.tools.allow
    defaults_tools = (
        agents_cfg.get("defaults", {}).get("tools", {}).get("allow", [])
    )
    _collect_tools(defaults_tools)

    # From top-level tools.allow
    top_tools = config.get("tools", {}).get("allow", [])
    _collect_tools(top_tools)

    # Per-agent tool overrides
    for entry in agents_cfg.get("list", []):
        if isinstance(entry, dict):
            per_agent_tools = entry.get("tools", {}).get("allow", [])
            _collect_tools(per_agent_tools)

    # -- 7. Agent → Tool edges (invokes) --------------------------------- #
    for aid in resolved_agent_ids:
        for tid in tool_ids:
            etype = EdgeType.INVOKES
            source = f"agent:{aid}"
            graph.edges.append(
                Edge(
                    id=_edge_id(source, tid, etype.value),
                    source=source,
                    target=tid,
                    type=etype,
                )
            )

    # -- 8. Scheduler node ----------------------------------------------- #
    cron_cfg: dict[str, Any] = config.get("cron", {})
    if cron_cfg.get("enabled") is True:
        sched_id = "scheduler:cron"
        graph.nodes.append(
            Node(id=sched_id, type=NodeType.SCHEDULER, label="Cron Scheduler")
        )
        for aid in resolved_agent_ids:
            etype = EdgeType.TRIGGERS
            target = f"agent:{aid}"
            graph.edges.append(
                Edge(
                    id=_edge_id(sched_id, target, etype.value),
                    source=sched_id,
                    target=target,
                    type=etype,
                )
            )

    # -- 9. Subagent surface --------------------------------------------- #
    subagents_cfg: dict[str, Any] = config.get("subagents", {})
    if subagents_cfg.get("allowAgents") is True:
        sub_id = "subagent_surface:default"
        graph.nodes.append(
            Node(
                id=sub_id,
                type=NodeType.SUBAGENT_SURFACE,
                label="Subagent Surface",
            )
        )
        for aid in resolved_agent_ids:
            etype = EdgeType.SPAWNS
            source = f"agent:{aid}"
            graph.edges.append(
                Edge(
                    id=_edge_id(source, sub_id, etype.value),
                    source=source,
                    target=sub_id,
                    type=etype,
                )
            )

    # -- 10. Extension nodes --------------------------------------------- #
    # From plugins.entries in config
    plugins_cfg: dict[str, Any] = config.get("plugins", {})
    for entry in plugins_cfg.get("entries", []):
        ext_name = entry if isinstance(entry, str) else (
            entry.get("name") if isinstance(entry, dict) else str(entry)
        )
        if ext_name:
            graph.nodes.append(
                Node(
                    id=f"extension:{ext_name}",
                    type=NodeType.EXTENSION,
                    label=ext_name,
                )
            )

    # From extensions/ directory on disk
    extensions_dir = openclaw_root / "extensions"
    if extensions_dir.is_dir():
        for child in sorted(extensions_dir.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                ext_name = child.name
                ext_id = f"extension:{ext_name}"
                if not any(n.id == ext_id for n in graph.nodes):
                    graph.nodes.append(
                        Node(
                            id=ext_id,
                            type=NodeType.EXTENSION,
                            label=ext_name,
                        )
                    )

    return graph
