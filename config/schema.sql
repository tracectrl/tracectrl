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
