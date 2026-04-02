"""Attack graph pipeline step — runs rules, scores paths, persists results."""

import hashlib
import json
import logging
from engine.db.client import execute
from engine.rules.prompt_injection import PromptInjectionRule
from engine.rules.excessive_agency import ExcessiveAgencyRule
from engine.rules.data_leakage import DataLeakageRule
from engine.pipeline.risk_scorer import compute_path_risk, severity_for_score
from engine.db.attack_graph import upsert_attack_paths, upsert_agent_risk_scores, upsert_system_risk

logger = logging.getLogger(__name__)


def run_attack_graph():
    agent_rows = execute(
        "SELECT agent_id, name, framework, role, model, tools_observed, "
        "observation_count, maturity FROM agent_inventory FINAL"
    )
    agent_cols = ["agent_id", "name", "framework", "role", "model",
                  "tools_observed", "observation_count", "maturity"]
    agents = [dict(zip(agent_cols, r)) for r in agent_rows]

    tool_rows = execute(
        "SELECT edge_id, agent_id, tool_name, tool_category, call_count, "
        "call_contexts FROM topology_tool_edges FINAL"
    )
    tool_cols = ["edge_id", "agent_id", "tool_name", "tool_category",
                 "call_count", "call_contexts"]
    tool_edges = [dict(zip(tool_cols, r)) for r in tool_rows]

    agent_edge_rows = execute(
        "SELECT edge_id, caller_agent_id, callee_agent_id, channel, "
        "observation_count FROM topology_agent_edges FINAL"
    )
    edge_cols = ["edge_id", "caller_agent_id", "callee_agent_id",
                 "channel", "observation_count"]
    agent_edges = [dict(zip(edge_cols, r)) for r in agent_edge_rows]

    if not agents:
        return

    # Run rules in dependency order
    r1 = PromptInjectionRule()
    injection_results = r1.evaluate(agents, tool_edges, agent_edges)

    r2 = ExcessiveAgencyRule()
    agency_results = r2.evaluate(agents, tool_edges, agent_edges,
                                  injection_results=injection_results)

    r3 = DataLeakageRule()
    leakage_results = r3.evaluate(agents, tool_edges, agent_edges,
                                   injection_results=injection_results)

    all_results = injection_results + agency_results + leakage_results
    if not all_results:
        logger.info("Attack graph: no vulnerabilities detected.")
        return

    # Score and persist paths
    paths = []
    agent_scores: dict[str, dict] = {}

    for result in all_results:
        tool_cat = "internal_api"
        input_src = "user"
        # Extract tool category from steps if available
        for step in result.steps:
            if step.node_type == "tool":
                # Parse category from description
                for cat in ("code_execution", "email", "external_api", "file_system"):
                    if cat in step.description:
                        tool_cat = cat
                        break
        # Check call_contexts for input source
        for edge in tool_edges:
            if edge["agent_id"] in result.agents_involved:
                contexts = json.loads(edge["call_contexts"]) if isinstance(edge["call_contexts"], str) else (edge["call_contexts"] or {})
                if isinstance(contexts, dict) and contexts.get("external", 0) > 0:
                    input_src = "external"
                    break

        score = compute_path_risk(result, tool_cat, input_src, len(result.steps))
        severity = severity_for_score(score)
        path_id = hashlib.md5(
            f"{result.rule_name}:{'|'.join(result.agents_involved)}:{tool_cat}".encode()
        ).hexdigest()[:16]

        paths.append({
            "path_id": path_id,
            "rule_id": result.rule_id,
            "rule_name": result.rule_name,
            "severity": severity,
            "owasp_tag": result.owasp_category,
            "title": result.title,
            "description": result.description,
            "agent_id": result.agents_involved[0] if result.agents_involved else "",
            "agents_involved": result.agents_involved,
            "path_nodes": result.path_nodes,
            "path_edges": result.path_edges,
            "path_steps": [{"node_id": s.node_id, "node_type": s.node_type,
                            "vulnerability": s.vulnerability, "description": s.description}
                           for s in result.steps],
            "risk_score": score,
        })

        # Accumulate per-agent scores
        for aid in result.agents_involved:
            if aid not in agent_scores:
                agent_scores[aid] = {"agent_id": aid, "risk_score": 0.0,
                                     "path_count": 0, "top_rule": "", "top_score": 0.0}
            agent_scores[aid]["path_count"] += 1
            if score > agent_scores[aid]["top_score"]:
                agent_scores[aid]["top_score"] = score
                agent_scores[aid]["risk_score"] = score
                agent_scores[aid]["top_rule"] = result.rule_name
                agent_scores[aid]["severity"] = severity

    upsert_attack_paths(paths)

    agent_risk_list = list(agent_scores.values())
    for a in agent_risk_list:
        a.pop("top_score", None)
        a["severity"] = severity_for_score(a["risk_score"])
    upsert_agent_risk_scores(agent_risk_list)

    # System risk
    learning = execute("SELECT count() FROM agent_inventory FINAL WHERE maturity = 'LEARNING'")
    learning_count = learning[0][0] if learning else 0
    max_score = max(p["risk_score"] for p in paths) if paths else 0.0
    critical_count = sum(1 for p in paths if p["severity"] in ("Critical", "High"))

    upsert_system_risk({
        "risk_score": max_score,
        "severity": severity_for_score(max_score),
        "critical_paths": critical_count,
        "agents_at_risk": len(agent_scores),
        "learning_agents": learning_count,
    })

    logger.info(f"Attack graph: {len(paths)} paths, {len(agent_scores)} agents at risk.")
