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
    import re as _re
    db = os.getenv("CLICKHOUSE_DB", "tracectrl")
    if not _re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', db):
        raise ValueError(f"Invalid CLICKHOUSE_DB value: {db!r}")
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
        f"""CREATE TABLE IF NOT EXISTS {db}.scan_topology (
            scan_id String, created_at DateTime, topology_json String
        ) ENGINE = ReplacingMergeTree(created_at) ORDER BY scan_id""",
        f"""CREATE TABLE IF NOT EXISTS {db}.scan_runs (
  scan_id        String,
  scanned_at     DateTime64(3, 'UTC'),
  workspace_path String,
  config_hash    String DEFAULT '',
  profile        String DEFAULT 'L1'
) ENGINE = ReplacingMergeTree()
ORDER BY (scan_id)""",
        f"""CREATE TABLE IF NOT EXISTS {db}.guardrail_violations (
            violation_id     String,
            trace_id         String,
            span_id          String,
            eval_span_id     String,
            agent_id         String,
            guardrail_name   String,
            judge_model      String,
            decision         Enum8('pass'=0, 'fail'=1, 'error'=2),
            reason           String,
            evidence         String,
            severity         Enum8('low'=0, 'medium'=1, 'high'=2, 'critical'=3),
            observed_at      DateTime64(3, 'UTC'),
            inserted_at      DateTime64(3, 'UTC')
        ) ENGINE = ReplacingMergeTree()
        ORDER BY (observed_at, violation_id)""",
        f"""CREATE TABLE IF NOT EXISTS {db}.guardrail_registry (
            agent_id            String,
            guardrail_name      String,
            severity            Enum8('low'=0, 'medium'=1, 'high'=2, 'critical'=3),
            mode                Enum8('monitoring'=0, 'blocking'=1),
            timing              Enum8('post_output'=0, 'pre_input'=1),
            judge_model         String,
            description         String,
            judge_prompt        String,
            health              Enum8('active'=0, 'error'=1, 'disabled'=2),
            health_reason       String,
            registered_at       DateTime64(3, 'UTC'),
            last_seen_at        DateTime64(3, 'UTC'),
            inserted_at         DateTime64(3, 'UTC')
        ) ENGINE = ReplacingMergeTree(last_seen_at)
        ORDER BY (agent_id, guardrail_name)""",
        # Add column for existing deployments — IF NOT EXISTS keeps this idempotent
        # for fresh installs (the CREATE above already includes it).
        "ALTER TABLE tracectrl.guardrail_registry ADD COLUMN IF NOT EXISTS judge_prompt String AFTER description",
        # --- TraceCtrl Guards (Protector Plus integration) ---
        # Global config (single row, id='global'). API-based external guardrail
        # provider config — endpoint, API key, which of the 7 guardrails are
        # enabled. SDK fetches this at startup; UI Settings page writes it.
        f"""CREATE TABLE IF NOT EXISTS {db}.protector_plus_config (
            id                 String DEFAULT 'global',
            endpoint_url       String,
            api_key            String,
            enabled_guardrails Array(String),
            updated_at         DateTime64(3, 'UTC')
        ) ENGINE = ReplacingMergeTree(updated_at)
        ORDER BY (id)""",
        # Provider discriminator on violations — distinguishes Protector Plus
        # violations from the existing judge-LLM ones. Default keeps existing
        # rows correct (they're all judge-LLM today).
        "ALTER TABLE tracectrl.guardrail_violations ADD COLUMN IF NOT EXISTS provider String DEFAULT 'judge_llm'",
        # Same provider discriminator on registry so the UI can chip them.
        "ALTER TABLE tracectrl.guardrail_registry ADD COLUMN IF NOT EXISTS provider String DEFAULT 'judge_llm'",
    ]
    client = get_client()
    for stmt in stmts:
        try:
            client.execute(stmt)
        except Exception as e:
            logger.warning("Schema stmt failed: %s — %s", stmt[:60], e)
