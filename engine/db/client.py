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
