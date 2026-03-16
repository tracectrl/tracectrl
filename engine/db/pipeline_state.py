"""Watermark read/write for pipeline state."""

from datetime import datetime, timedelta
from engine.db.client import execute


def get_watermark() -> datetime:
    """Get the last processed timestamp. Uses FINAL for ReplacingMergeTree correctness."""
    rows = execute(
        "SELECT value FROM pipeline_state FINAL WHERE key = 'last_processed_at'"
    )
    if rows:
        return datetime.fromisoformat(rows[0][0])
    return datetime.utcnow() - timedelta(hours=24)


def set_watermark(ts: datetime):
    """Advance the watermark to the given timestamp."""
    execute(
        "INSERT INTO pipeline_state (key, value, updated_at) VALUES",
        [("last_processed_at", ts.isoformat(), datetime.utcnow())],
    )
