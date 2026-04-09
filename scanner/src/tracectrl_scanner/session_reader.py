"""Read OpenClaw session files."""

from __future__ import annotations

import json
from pathlib import Path


def read_sessions(root: Path, agent_id: str) -> list[dict]:
    """Read all session messages for a given agent.

    Scans ``agents/<agent_id>/sessions/*.jsonl`` and returns every message
    across all session files.  Each line in a ``.jsonl`` file is expected to
    be a JSON object representing a single message in the session.

    Args:
        root: Path to the OpenClaw installation root.
        agent_id: The agent identifier.

    Returns:
        A list of message dictionaries aggregated from all session files,
        ordered by file name then by line position.
    """
    sessions_dir = root / "agents" / agent_id / "sessions"
    if not sessions_dir.is_dir():
        return []

    messages: list[dict] = []
    for session_file in sorted(sessions_dir.glob("*.jsonl")):
        for line in session_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                messages.append(json.loads(line))

    return messages
