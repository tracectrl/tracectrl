"""Main pipeline function with watermark logic."""

import logging
from datetime import datetime
from engine.db.spans import fetch_new_spans
from engine.db.inventory import update_agent_inventory
from engine.db.topology import update_topology
from engine.db.pipeline_state import get_watermark, set_watermark

logger = logging.getLogger(__name__)


def run_pipeline():
    """
    Sprint 1 pipeline — runs every PIPELINE_INTERVAL_SECONDS.
    Steps: fetch -> inventory -> topology -> watermark.
    Attack graph and risk scoring added in Sprint 2.
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

        set_watermark(datetime.utcnow())
        logger.info(f"Pipeline run complete. Processed {len(spans)} spans.")

    except Exception as e:
        logger.error(f"Pipeline run failed: {e}. Watermark not advanced.")
        raise
