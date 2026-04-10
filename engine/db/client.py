"""ClickHouse connection and query helpers. Thread-safe via thread-local clients."""

import os
import logging
import threading
from clickhouse_driver import Client

logger = logging.getLogger(__name__)

_local = threading.local()


def get_client() -> Client:
    """Return a thread-local ClickHouse client (one connection per thread)."""
    if not hasattr(_local, "client"):
        _local.client = Client(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
            database=os.getenv("CLICKHOUSE_DB", "tracectrl"),
        )
    return _local.client


def execute(query: str, params=None):
    """Execute a query and return results."""
    client = get_client()
    return client.execute(query, params)


def ensure_schema() -> None:
    """Ensure all required tables exist. Safe to call on every startup."""
    db = os.getenv("CLICKHOUSE_DB", "tracectrl")
    stmts = [
        f"CREATE DATABASE IF NOT EXISTS {db}",
        f"""CREATE TABLE IF NOT EXISTS {db}.agent_inventory (
            agent_id String, name String, framework String, role String,
            model String, tools_observed Array(String), system_prompt String,
            system_prompt_hash String, prompt_template String, run_count UInt32,
            observation_count UInt32, maturity String, first_seen DateTime,
            last_seen DateTime, updated_at DateTime
        ) ENGINE = ReplacingMergeTree(updated_at) ORDER BY agent_id""",
        f"""CREATE TABLE IF NOT EXISTS {db}.topology_agent_edges (
            edge_id String, caller_agent_id String, callee_agent_id String,
            channel String, observation_count UInt32, confidence String,
            first_seen DateTime, last_seen DateTime, updated_at DateTime
        ) ENGINE = ReplacingMergeTree(updated_at) ORDER BY edge_id""",
        f"""CREATE TABLE IF NOT EXISTS {db}.topology_tool_edges (
            edge_id String, agent_id String, tool_name String, tool_category String,
            call_count UInt32, call_contexts String, last_parameters String,
            error_count UInt32, first_seen DateTime, last_seen DateTime, updated_at DateTime
        ) ENGINE = ReplacingMergeTree(updated_at) ORDER BY edge_id""",
        f"""CREATE TABLE IF NOT EXISTS {db}.pipeline_state (
            key String, value String, updated_at DateTime
        ) ENGINE = ReplacingMergeTree(updated_at) ORDER BY key""",
        f"""CREATE TABLE IF NOT EXISTS {db}.attack_paths (
            path_id String, rule_name String, owasp_category String,
            agents_involved Array(String), path_steps String, risk_score Float32,
            severity String, computed_at DateTime, updated_at DateTime
        ) ENGINE = ReplacingMergeTree(updated_at) ORDER BY path_id""",
        f"""CREATE TABLE IF NOT EXISTS {db}.agent_risk_scores (
            agent_id String, risk_score Float32, severity String, path_count UInt32,
            top_rule String, computed_at DateTime, updated_at DateTime
        ) ENGINE = ReplacingMergeTree(updated_at) ORDER BY agent_id""",
        f"""CREATE TABLE IF NOT EXISTS {db}.system_risk (
            id UInt8 DEFAULT 1, risk_score Float32, severity String,
            critical_paths UInt32, agents_at_risk UInt32, learning_agents UInt32,
            computed_at DateTime, updated_at DateTime
        ) ENGINE = ReplacingMergeTree(updated_at) ORDER BY id""",
        f"""CREATE TABLE IF NOT EXISTS {db}.scan_results (
            scan_id String, scanned_at DateTime, openclaw_path String, profile String,
            check_id String, section String, title String, severity String,
            passed UInt8, finding String, remediation String, config_path String
        ) ENGINE = MergeTree() ORDER BY (scan_id, check_id)""",
    ]
    client = get_client()
    for stmt in stmts:
        try:
            client.execute(stmt)
        except Exception as e:
            logger.warning("Schema stmt failed: %s — %s", stmt[:60], e)
