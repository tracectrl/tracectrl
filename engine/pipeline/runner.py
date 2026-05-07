"""Main pipeline function — reprocesses all spans every run."""

import logging
from engine.db.spans import fetch_all_spans
from engine.db.inventory import update_agent_inventory
from engine.db.topology import update_topology
from engine.db.violations import update_violations
from engine.db.guardrail_registry import update_guardrail_registry
from engine.pipeline.attack_graph_runner import run_attack_graph

logger = logging.getLogger(__name__)


def run_pipeline():
    """
    Sprint 2 pipeline — runs every PIPELINE_INTERVAL_SECONDS.
    Steps: fetch all spans -> inventory -> topology -> attack_graphs.
    ReplacingMergeTree handles deduplication automatically via FINAL queries.
    """
    logger.info("Pipeline run starting. Reprocessing all spans.")

    try:
        spans = fetch_all_spans()
        if not spans:
            logger.info("No spans in database. Skipping pipeline run.")
            return

        logger.info(f"Processing {len(spans)} total spans.")
        update_agent_inventory(spans)
        update_topology(spans)
        update_violations(spans)
        update_guardrail_registry(spans)

        # Run attack graph analysis
        run_attack_graph()

        logger.info(f"Pipeline run complete. Processed {len(spans)} spans.")

    except Exception as e:
        logger.error(f"Pipeline run failed: {e}")
        raise
