"""Main pipeline function with watermark logic."""

import logging
from datetime import datetime
from engine.db.spans import fetch_new_spans
from engine.db.inventory import update_agent_inventory
from engine.db.topology import update_topology
from engine.pipeline.attack_graph import generate_attack_paths
from engine.pipeline.attack_graph_runner import run_attack_graph
from engine.db.pipeline_state import get_watermark, set_watermark

logger = logging.getLogger(__name__)


def run_pipeline():
    """
    Sprint 2 pipeline — runs every PIPELINE_INTERVAL_SECONDS.
    Steps: fetch -> inventory -> topology -> attack_graphs -> watermark.
    """
    watermark = get_watermark()
    logger.info(f"Pipeline run starting. Processing spans since {watermark}")

    try:
        spans = fetch_new_spans(since=watermark)
        if not spans:
            logger.info("No new spans. Skipping pipeline run.")
            return  # Do NOT advance watermark on empty result

        update_agent_inventory(spans)
        update_topology(spans)

        # Run both attack graph implementations
        run_attack_graph()  # Sprint 2 risk scoring
        generate_attack_paths()  # New spec-based attack paths

        set_watermark(datetime.utcnow())
        logger.info(f"Pipeline run complete. Processed {len(spans)} spans.")

    except Exception as e:
        logger.error(f"Pipeline run failed: {e}. Watermark not advanced.")
        raise
