"""Protector Plus / TraceCtrl Guards configuration storage.

Single global row (id='global') in `protector_plus_config`. The SDK fetches
this at agent startup; the UI Settings page writes it. ReplacingMergeTree
upserts on `id`, so successive writes overwrite the previous row.
"""

import logging
from datetime import datetime, timezone
from engine.db.client import execute

logger = logging.getLogger(__name__)


# The 7 Protector Plus guardrails the UI exposes as toggles. Validating
# against this set keeps junk out of the array column and gives the UI a
# stable contract.
PROTECTOR_GUARDRAILS = {
    "llm",
    "keyword",
    "regex",
    "pii",
    "vector",
    "content_moderation",
    "system_prompt_protection",
}


def get_protector_config() -> dict | None:
    """Return the global Protector Plus config, or None if never set."""
    rows = execute(
        """
        SELECT endpoint_url, api_key, enabled_guardrails, updated_at
        FROM protector_plus_config FINAL
        WHERE id = 'global'
        """
    )
    if not rows:
        return None
    endpoint_url, api_key, enabled_guardrails, updated_at = rows[0]
    return {
        "endpoint_url": endpoint_url,
        "api_key": api_key,
        "enabled_guardrails": list(enabled_guardrails or []),
        "updated_at": updated_at,
    }


def set_protector_config(
    endpoint_url: str,
    api_key: str,
    enabled_guardrails: list[str],
) -> dict:
    """Upsert the global Protector Plus config.

    Filters `enabled_guardrails` to only known keys (see PROTECTOR_GUARDRAILS)
    to keep the array clean. Returns the row that was written.
    """
    cleaned = [g for g in enabled_guardrails if g in PROTECTOR_GUARDRAILS]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    execute(
        "INSERT INTO protector_plus_config (id, endpoint_url, api_key, enabled_guardrails, updated_at) VALUES",
        [("global", endpoint_url, api_key, cleaned, now)],
    )
    logger.info(
        "set_protector_config: endpoint=%s, enabled=%s",
        endpoint_url,
        cleaned,
    )
    return {
        "endpoint_url": endpoint_url,
        "api_key": api_key,
        "enabled_guardrails": cleaned,
        "updated_at": now,
    }


def redact_api_key(key: str) -> str:
    """Show first 4 chars and `***` — never log or transmit the rest unless
    the caller is the SDK fetch endpoint."""
    if not key:
        return ""
    if len(key) <= 4:
        return "***"
    return key[:4] + "***" + key[-4:]
