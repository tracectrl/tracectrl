"""Parse OpenClaw configuration files (JSON5 format)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pyjson5


def parse_config(root: Path) -> dict:
    """Read and parse the top-level ``openclaw.json`` config file.

    Args:
        root: Path to the OpenClaw installation root.

    Returns:
        Parsed configuration as a dictionary.

    Raises:
        FileNotFoundError: If ``openclaw.json`` does not exist.
    """
    config_path = root / "openclaw.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    return pyjson5.decode(config_path.read_text(encoding="utf-8"))


def parse_soul(root: Path, agent_id: str) -> Optional[str]:
    """Read the SOUL.md file for a given agent.

    Args:
        root: Path to the OpenClaw installation root.
        agent_id: The agent identifier.

    Returns:
        Contents of ``agents/<agent_id>/agent/SOUL.md``, or ``None`` if the
        file does not exist.
    """
    soul_path = root / "agents" / agent_id / "agent" / "SOUL.md"
    if not soul_path.exists():
        return None
    return soul_path.read_text(encoding="utf-8")


def parse_plugin_manifest(root: Path, plugin_id: str) -> Optional[dict]:
    """Read and parse the plugin manifest for a given extension.

    Args:
        root: Path to the OpenClaw installation root.
        plugin_id: The plugin/extension identifier.

    Returns:
        Parsed manifest as a dictionary, or ``None`` if the manifest file
        does not exist.
    """
    manifest_path = root / "extensions" / plugin_id / "openclaw.plugin.json"
    if not manifest_path.exists():
        return None
    return pyjson5.decode(manifest_path.read_text(encoding="utf-8"))
