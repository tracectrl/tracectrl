"""Datetime helpers for the ClickHouse layer.

Kept separate from `client.py` so it doesn't drag the `clickhouse-driver`
dependency into unit tests that only care about the time-shaping helpers.
"""

from datetime import datetime, timezone


def as_utc(dt):
    """Ensure a datetime returned from ClickHouse is tz-aware UTC.

    ClickHouse columns declared `DateTime64(3, 'UTC')` are stored as UTC, but
    `clickhouse-driver` returns NAIVE `datetime` objects. Pydantic then
    serializes those without a `Z` / `+00:00` suffix, and the browser's
    `new Date(iso)` interprets a no-tz string as local time — making the UI
    display UTC clock values as if they were local. Stamping `tzinfo=UTC`
    here is what lets `toLocaleString()` correctly shift to the viewer's
    timezone. No-op for already-aware datetimes or None.
    """
    if dt is None or not isinstance(dt, datetime):
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
