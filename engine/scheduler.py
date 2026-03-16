"""APScheduler: runs pipeline every N seconds."""

import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _run_pipeline_sync():
    """Run the pipeline. Called by APScheduler on interval."""
    from engine.pipeline.runner import run_pipeline
    try:
        run_pipeline()
    except Exception:
        logger.exception("Pipeline run failed")


def start_scheduler():
    global _scheduler
    interval = int(os.getenv("PIPELINE_INTERVAL_SECONDS", "60"))
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_run_pipeline_sync, "interval", seconds=interval, id="pipeline")
    _scheduler.start()
    logger.info(f"Pipeline scheduler started (interval={interval}s)")


def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info("Pipeline scheduler stopped")
