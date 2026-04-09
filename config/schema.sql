CREATE DATABASE IF NOT EXISTS tracectrl;

-- Note: The otel_traces table is auto-created by the OTel Collector ClickHouse exporter
-- (create_schema: true in otel-collector.yaml). It uses the exporter's standard schema
-- with Map columns for SpanAttributes/ResourceAttributes.
-- The tracectrl.* attributes are stored inside SpanAttributes and extracted by the pipeline.

-- Agent Inventory (persistent, no TTL)
CREATE TABLE IF NOT EXISTS tracectrl.agent_inventory (
    agent_id            String,
    name                String,
    framework           String,
    role                String,
    model               String,
    tools_observed      Array(String),
    system_prompt       String,
    system_prompt_hash  String,
    prompt_template     String,
    run_count           UInt32,
    observation_count   UInt32,
    maturity            String,
    first_seen          DateTime,
    last_seen           DateTime,
    updated_at          DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY agent_id;

-- Agent-to-Agent topology edges
CREATE TABLE IF NOT EXISTS tracectrl.topology_agent_edges (
    edge_id             String,
    caller_agent_id     String,
    callee_agent_id     String,
    channel             String,
    observation_count   UInt32,
    confidence          String,
    first_seen          DateTime,
    last_seen           DateTime,
    updated_at          DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY edge_id;

-- Agent-to-Tool topology edges
CREATE TABLE IF NOT EXISTS tracectrl.topology_tool_edges (
    edge_id             String,
    agent_id            String,
    tool_name           String,
    tool_category       String,
    call_count          UInt32,
    call_contexts       String,
    last_parameters     String,
    error_count         UInt32,
    first_seen          DateTime,
    last_seen           DateTime,
    updated_at          DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY edge_id;

-- Pipeline watermark state
CREATE TABLE IF NOT EXISTS tracectrl.pipeline_state (
    key         String,
    value       String,
    updated_at  DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY key;

-- Seed watermark to 24 hours ago
INSERT INTO tracectrl.pipeline_state (key, value, updated_at)
VALUES ('last_processed_at', toString(now() - INTERVAL 24 HOUR), now());

-- Attack paths discovered by TAGAAI rules
CREATE TABLE IF NOT EXISTS tracectrl.attack_paths (
    path_id         String,
    rule_name       String,
    owasp_category  String,
    agents_involved Array(String),
    path_steps      String,
    risk_score      Float32,
    severity        String,
    computed_at     DateTime,
    updated_at      DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY path_id;

-- Per-agent risk scores
CREATE TABLE IF NOT EXISTS tracectrl.agent_risk_scores (
    agent_id        String,
    risk_score      Float32,
    severity        String,
    path_count      UInt32,
    top_rule        String,
    computed_at     DateTime,
    updated_at      DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY agent_id;

-- System-wide risk summary (single row)
CREATE TABLE IF NOT EXISTS tracectrl.system_risk (
    id              UInt8 DEFAULT 1,
    risk_score      Float32,
    severity        String,
    critical_paths  UInt32,
    agents_at_risk  UInt32,
    learning_agents UInt32,
    computed_at     DateTime,
    updated_at      DateTime
) ENGINE = ReplacingMergeTree(updated_at)
  ORDER BY id;

-- Scan results from static OpenClaw analysis
CREATE TABLE IF NOT EXISTS tracectrl.scan_results (
    scan_id        String,
    scanned_at     DateTime,
    openclaw_path  String,
    profile        String,
    check_id       String,
    section        String,
    title          String,
    severity       String,
    passed         UInt8,
    finding        String,
    remediation    String,
    config_path    String
) ENGINE = MergeTree()
  ORDER BY (scan_id, check_id);
