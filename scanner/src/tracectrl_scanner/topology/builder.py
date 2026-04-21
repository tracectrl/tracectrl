"""Static topology builder for OpenClaw configurations.

Parses an OpenClaw config dict and produces a TopologyGraph representing
all nodes (ingress channels, agents, tools, LLM providers, etc.) and the
edges between them.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from ..discovery import list_skills
from .models import Edge, EdgeType, Node, NodeType, TopologyGraph

# Channels that accept messages from the public internet.
_INTERNET_CHANNELS = {"whatsapp", "telegram", "discord", "slack", "web", "api"}

# Plugin names that are actually LLM providers (OpenClaw uses plugins for model access).
_LLM_PLUGIN_NAMES = {
    "anthropic", "openai", "google", "azure", "vllm", "ollama",
    "groq", "mistral", "cohere", "together", "deepseek", "bedrock",
}

# Keys whose presence (with a truthy value) signals a channel is configured.
_CHANNEL_CONFIG_SIGNALS = {"token", "bot_token", "api_key", "webhook_url", "app_id"}

# Skills with known data-write / sensitive-read capabilities.
_HIGH_RISK_SKILLS = {
    "notion": "read/write Notion pages and databases",
    "github": "read/write GitHub repositories and issues",
    "gitlab": "read/write GitLab repositories",
    "gmail": "send email and read inbox",
    "google-mail": "send email and read inbox",
    "google-docs": "read/write Google Docs",
    "google-drive": "read/write Google Drive files",
    "gdrive": "read/write Google Drive files",
    "google-sheets": "read/write Google Sheets",
    "sheets": "read/write Google Sheets",
    "jira": "read/write Jira issues",
    "confluence": "read/write Confluence pages",
    "salesforce": "access CRM customer data",
    "hubspot": "access CRM customer data",
    "slack": "post messages to Slack",
    "linear": "read/write Linear issues",
    "airtable": "read/write Airtable bases",
    "postgres": "direct database access",
    "mysql": "direct database access",
    "mongodb": "direct database access",
    "database": "direct database access",
    "file": "read/write local filesystem",
    "filesystem": "read/write local filesystem",
    "code-interpreter": "execute arbitrary code",
    "python": "execute Python code",
    "jupyter": "execute Jupyter notebooks",
    "aws": "AWS cloud API access",
    "azure": "Azure cloud API access",
    "gcp": "Google Cloud Platform access",
    "sendgrid": "send bulk email",
    "mailchimp": "send bulk email",
    "twilio": "send SMS messages",
    "stripe": "payment and billing access",
}

_CRED_KEY_NAMES = {"apikey", "api_key", "token", "secret", "password", "key"}


def _mask_token(value: str) -> str:
    """Return a masked version of a secret: show last 4 chars only."""
    if not value or len(value) < 5:
        return "••••"
    return "••••" + value[-4:]


def _key_status(value: Any) -> str:
    """Classify a credential value as 'env_var', 'plaintext', or 'none'."""
    if not value or not isinstance(value, str):
        return "none"
    if re.match(r"^\$\{.+\}$", value):
        return "env_var"
    return "plaintext"


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
            raw_token = (
                ch_cfg.get("botToken") or ch_cfg.get("token")
                or ch_cfg.get("apiKey") or ""
            ) if isinstance(ch_cfg, dict) else ""
            props: dict[str, Any] = {
                "channel": ch_name,
                "dm_policy": ch_cfg.get("dmPolicy", "") if isinstance(ch_cfg, dict) else "",
                "allow_from": ch_cfg.get("allowFrom", []) if isinstance(ch_cfg, dict) else [],
                "group_policy": ch_cfg.get("groupPolicy", "") if isinstance(ch_cfg, dict) else "",
                "streaming": ch_cfg.get("streaming", "") if isinstance(ch_cfg, dict) else "",
                "has_token": bool(raw_token),
                "token_tail": _mask_token(raw_token) if raw_token else "",
            }
            graph.nodes.append(
                Node(id=node_id, type=NodeType.INGRESS, label=ch_name.title(), properties=props)
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

    defaults_cfg: dict[str, Any] = agents_cfg.get("defaults", {})
    heartbeat_cfg = defaults_cfg.get("heartbeat", {})
    heartbeat_str = ""
    if isinstance(heartbeat_cfg, dict) and heartbeat_cfg.get("every"):
        heartbeat_str = f"every {heartbeat_cfg['every']}"
        if heartbeat_cfg.get("target"):
            heartbeat_str += f" via {heartbeat_cfg['target']}"

    for aid in resolved_agent_ids:
        # Read soul.md excerpt if available
        soul_excerpt = ""
        try:
            soul_path = openclaw_root / "agents" / aid / "agent" / "SOUL.md"
            if soul_path.exists():
                soul_excerpt = soul_path.read_text(encoding="utf-8")[:500].strip()
        except Exception:
            pass

        agent_props: dict[str, Any] = {
            "primary_model": (
                defaults_cfg.get("model", {}).get("primary", "")
                if isinstance(defaults_cfg.get("model"), dict) else ""
            ),
            "workspace": defaults_cfg.get("workspace", ""),
            "max_concurrent": defaults_cfg.get("maxConcurrent", ""),
            "compaction_mode": (
                defaults_cfg.get("compaction", {}).get("mode", "")
                if isinstance(defaults_cfg.get("compaction"), dict) else ""
            ),
            "heartbeat": heartbeat_str,
            "soul_excerpt": soul_excerpt,
        }
        graph.nodes.append(
            Node(id=f"agent:{aid}", type=NodeType.AGENT, label=aid, properties=agent_props)
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

    # Models live in agents.defaults.models, keyed as "<provider>/<model-id>"
    agent_models: dict[str, Any] = defaults_cfg.get("models", {})
    primary_model: str = (
        defaults_cfg.get("model", {}).get("primary", "")
        if isinstance(defaults_cfg.get("model"), dict) else ""
    )

    for prov_name, prov_cfg in providers.items():
        node_id = f"llm:{prov_name}"
        prov_dict = prov_cfg if isinstance(prov_cfg, dict) else {}
        raw_key = prov_dict.get("apiKey", "")

        # Collect models from agents.defaults.models that belong to this provider
        prefix = f"{prov_name}/"
        agent_model_list = [k for k in agent_models if k.startswith(prefix)]
        # Also fall back to the provider's own models list/dict if populated
        prov_models_raw = prov_dict.get("models", [])
        if isinstance(prov_models_raw, dict):
            prov_model_list = list(prov_models_raw.keys())
        elif isinstance(prov_models_raw, list):
            prov_model_list = [str(m) for m in prov_models_raw if m]
        else:
            prov_model_list = []
        # Merge, deduplicate, preserve order
        all_models = list(dict.fromkeys(agent_model_list + prov_model_list))

        # Which one is the active primary?
        active_model = primary_model if primary_model.startswith(prefix) else ""

        llm_props: dict[str, Any] = {
            "base_url": prov_dict.get("baseUrl", ""),
            "api_key_status": _key_status(raw_key),
            "api_key_tail": _mask_token(raw_key) if raw_key and _key_status(raw_key) == "plaintext" else "",
            "models": all_models,
            "primary_model": active_model,
        }
        graph.nodes.append(
            Node(id=node_id, type=NodeType.LLM_PROVIDER, label=prov_name, properties=llm_props)
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

    web_cfg: dict[str, Any] = config.get("tools", {}).get("web", {})

    def _collect_tools(tools_list: list[Any]) -> None:
        for t in tools_list:
            name = t if isinstance(t, str) else (t.get("name") if isinstance(t, dict) else str(t))
            if name and name not in seen_tools:
                seen_tools.add(name)
                node_id = f"tool:{name}"
                tool_props: dict[str, Any] = {
                    "dangerous": name in ("bash", "shell", "exec"),
                    "wildcard": name == "*",
                }
                if name == "web_fetch":
                    tool_props["allowed_domains"] = (
                        web_cfg.get("fetch", {}).get("allowedDomains", [])
                    )
                graph.nodes.append(
                    Node(id=node_id, type=NodeType.TOOL, label=name, properties=tool_props)
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

    # Detect tools from enabled flags (web.search, web.fetch, exec)
    tools_cfg = config.get("tools", {})
    if isinstance(tools_cfg, dict):
        # Check web.search and web.fetch
        web_tools = tools_cfg.get("web", {})
        if isinstance(web_tools, dict):
            if web_tools.get("search", {}).get("enabled"):
                _collect_tools(["web_search"])
            if web_tools.get("fetch", {}).get("enabled"):
                _collect_tools(["web_fetch"])

        # Check exec tool - add with security level property
        exec_cfg = tools_cfg.get("exec", {})
        if isinstance(exec_cfg, dict) and exec_cfg.get("security"):
            exec_security = exec_cfg.get("security")
            node_id = "tool:exec"
            if node_id not in seen_tools:
                seen_tools.add("exec")
                tool_props: dict[str, Any] = {
                    "dangerous": True,
                    "security_level": exec_security,
                }
                graph.nodes.append(
                    Node(id=node_id, type=NodeType.TOOL, label="exec", properties=tool_props)
                )
                tool_ids.append(node_id)

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

    # -- 8. Scheduler nodes (cron + heartbeat) ----------------------------- #
    cron_cfg: dict[str, Any] = config.get("cron", {})
    if cron_cfg.get("enabled") is True:
        # Read individual jobs from <root>/cron/jobs.json
        cron_jobs: list[dict[str, Any]] = []
        jobs_file = openclaw_root / "cron" / "jobs.json"
        if jobs_file.exists():
            import json as _json
            try:
                jobs_data = _json.loads(jobs_file.read_text())
                cron_jobs = [j for j in jobs_data.get("jobs", []) if isinstance(j, dict)]
            except Exception:
                cron_jobs = []

        sched_id = "scheduler:cron"
        # Summarise jobs into a list stored on the single node
        jobs_summary = [
            {
                "id": j.get("id", ""),
                "name": j.get("name", j.get("id", "")),
                "expr": j.get("schedule", {}).get("expr", ""),
                "timezone": j.get("timezone", ""),
                "enabled": j.get("enabled", True),
                "action_type": j.get("action", {}).get("type", ""),
                "description": j.get("description", ""),
                "session_target": j.get("sessionTarget", ""),
            }
            for j in cron_jobs
        ]
        graph.nodes.append(
            Node(
                id=sched_id,
                type=NodeType.SCHEDULER,
                label="Cron Scheduler",
                properties={
                    "enabled": True,
                    "type": "cron",
                    "job_count": len(jobs_summary),
                    "jobs": jobs_summary,
                },
            )
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

    # Heartbeat is a scheduler even when cron is disabled
    heartbeat_cfg: dict[str, Any] = (
        config.get("agents", {}).get("defaults", {}).get("heartbeat", {})
    )
    if isinstance(heartbeat_cfg, dict) and heartbeat_cfg.get("every"):
        hb_id = "scheduler:heartbeat"
        hb_target = heartbeat_cfg.get("target", "")
        hb_to = heartbeat_cfg.get("to", "")
        graph.nodes.append(
            Node(
                id=hb_id,
                type=NodeType.SCHEDULER,
                label="Heartbeat",
                properties={
                    "enabled": True,
                    "type": "heartbeat",
                    "interval": heartbeat_cfg.get("every", ""),
                    "target": hb_target,
                    "to": str(hb_to) if hb_to else "",
                },
            )
        )
        for aid in resolved_agent_ids:
            etype = EdgeType.TRIGGERS
            target = f"agent:{aid}"
            graph.edges.append(
                Edge(
                    id=_edge_id(hb_id, target, etype.value),
                    source=hb_id,
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

    # -- 10. Extension / plugin nodes -------------------------------------- #
    # Collect all plugin names from config (plugins.allow, plugins.entries) and disk
    existing_node_ids = {n.id for n in graph.nodes}
    extension_ids: list[str] = []

    all_plugin_names: list[str] = []
    plugins_cfg: dict[str, Any] = config.get("plugins", {})
    raw_entries = plugins_cfg.get("entries", {})
    entries_list = list(raw_entries.keys()) if isinstance(raw_entries, dict) else list(raw_entries)
    raw_allow = plugins_cfg.get("allow", [])
    allow_list = list(raw_allow) if isinstance(raw_allow, list) else []
    for entry in entries_list + allow_list:
        name = entry if isinstance(entry, str) else (
            entry.get("name") if isinstance(entry, dict) else str(entry)
        )
        if name:
            all_plugin_names.append(name)

    extensions_dir = openclaw_root / "extensions"
    if extensions_dir.is_dir():
        for child in sorted(extensions_dir.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                if child.name not in all_plugin_names:
                    all_plugin_names.append(child.name)

    for ext_name in all_plugin_names:
        # Promote known LLM providers — skip if already exists as llm: node
        if ext_name.lower() in _LLM_PLUGIN_NAMES:
            llm_id = f"llm:{ext_name}"
            if llm_id not in existing_node_ids:
                graph.nodes.append(
                    Node(id=llm_id, type=NodeType.LLM_PROVIDER, label=ext_name)
                )
                existing_node_ids.add(llm_id)
                provider_ids.append(llm_id)
                # Add agent → provider edges
                for aid in resolved_agent_ids:
                    etype = EdgeType.CALLS
                    source = f"agent:{aid}"
                    graph.edges.append(
                        Edge(id=_edge_id(source, llm_id, etype.value), source=source, target=llm_id, type=etype)
                    )
        else:
            # If a same-named ingress node already exists (e.g. telegram is both a
            # channel and a plugin), reuse the ingress node rather than creating a
            # duplicate extension node. Still wire agent → ingress (hooks_into) so
            # the bidirectional relationship is visible in the graph.
            ingress_id = f"ingress:{ext_name}"
            if ingress_id in existing_node_ids:
                for aid in resolved_agent_ids:
                    etype = EdgeType.HOOKS_INTO
                    source = f"agent:{aid}"
                    graph.edges.append(
                        Edge(
                            id=_edge_id(source, ingress_id, etype.value),
                            source=source,
                            target=ingress_id,
                            type=etype,
                        )
                    )
                continue

            ext_id = f"extension:{ext_name}"
            if ext_id not in existing_node_ids:
                ext_entry = raw_entries.get(ext_name, {}) if isinstance(raw_entries, dict) else {}
                ext_enabled = ext_entry.get("enabled", True) if isinstance(ext_entry, dict) else True
                graph.nodes.append(
                    Node(
                        id=ext_id,
                        type=NodeType.EXTENSION,
                        label=ext_name,
                        properties={"enabled": ext_enabled},
                    )
                )
                existing_node_ids.add(ext_id)
                extension_ids.append(ext_id)

    # -- 11. Agent → Extension edges (uses) -------------------------------- #
    for aid in resolved_agent_ids:
        for ext_id in extension_ids:
            etype = EdgeType.HOOKS_INTO
            source = f"agent:{aid}"
            graph.edges.append(
                Edge(id=_edge_id(source, ext_id, etype.value), source=source, target=ext_id, type=etype)
            )

    # -- 12. Skill nodes from skills.entries and filesystem ----------------- #
    skills_cfg: dict[str, Any] = config.get("skills", {})
    skill_entries: dict[str, Any] = skills_cfg.get("entries", {})
    skill_ids: list[str] = []
    existing_node_ids = {n.id for n in graph.nodes}

    # First, add skills from config (skills.entries)
    if isinstance(skill_entries, dict):
        for skill_name, skill_cfg in skill_entries.items():
            skill_id = f"skill:{skill_name}"
            if skill_id in existing_node_ids:
                continue
            skill_props: dict[str, Any] = {}
            if isinstance(skill_cfg, dict):
                cred_value = ""
                cred_key = ""
                for k, v in skill_cfg.items():
                    if k.lower() in _CRED_KEY_NAMES and isinstance(v, str):
                        cred_value = v
                        cred_key = k
                        break
                skill_props["has_credential"] = bool(cred_value)
                skill_props["credential_status"] = _key_status(cred_value) if cred_value else "none"
                skill_props["credential_key"] = cred_key
                skill_props["credential_tail"] = _mask_token(cred_value) if cred_value and _key_status(cred_value) == "plaintext" else ""
            skill_props["risk_level"] = "high" if skill_name.lower() in _HIGH_RISK_SKILLS else "unknown"
            skill_props["capability"] = _HIGH_RISK_SKILLS.get(skill_name.lower(), "")
            graph.nodes.append(
                Node(id=skill_id, type=NodeType.SKILL, label=skill_name, properties=skill_props)
            )
            existing_node_ids.add(skill_id)
            skill_ids.append(skill_id)

    # Second, add skills discovered from filesystem (bundled/installed skills)
    discovered_skills = list_skills(openclaw_root)
    for skill_name in discovered_skills:
        skill_id = f"skill:{skill_name}"
        if skill_id in existing_node_ids:
            continue
        skill_props: dict[str, Any] = {
            "has_credential": False,
            "credential_status": "none",
            "credential_key": "",
            "credential_tail": "",
            "risk_level": "high" if skill_name.lower() in _HIGH_RISK_SKILLS else "unknown",
            "capability": _HIGH_RISK_SKILLS.get(skill_name.lower(), ""),
        }
        graph.nodes.append(
            Node(id=skill_id, type=NodeType.SKILL, label=skill_name, properties=skill_props)
        )
        existing_node_ids.add(skill_id)
        skill_ids.append(skill_id)

    # Create edges from agents to all skills
    for aid in resolved_agent_ids:
        for skill_id in skill_ids:
            etype = EdgeType.INVOKES
            source = f"agent:{aid}"
            graph.edges.append(
                Edge(
                    id=_edge_id(source, skill_id, etype.value),
                    source=source,
                    target=skill_id,
                    type=etype,
                )
            )

    return graph
