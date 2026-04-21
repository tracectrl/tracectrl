"""Discover OpenClaw installations on the local filesystem."""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_PATH = Path.home() / ".openclaw"


def discover(explicit_path: str | Path | None = None) -> Path:
    """Find and validate an OpenClaw installation directory.

    Resolution order:
        1. *explicit_path* argument (if provided)
        2. ``TRACECTRL_OPENCLAW_PATH`` environment variable
        3. ``~/.openclaw/``

    Returns the resolved :class:`Path` to the installation root.

    Raises:
        FileNotFoundError: If no valid OpenClaw installation can be located.
    """
    candidates: list[Path] = []

    if explicit_path is not None:
        candidates.append(Path(explicit_path))

    env_path = os.environ.get("TRACECTRL_OPENCLAW_PATH")
    if env_path:
        candidates.append(Path(env_path))

    candidates.append(_DEFAULT_PATH)

    for path in candidates:
        resolved = path.expanduser().resolve()
        if resolved.is_dir() and (resolved / "openclaw.json").exists():
            return resolved

    searched = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(
        f"No OpenClaw installation found. Searched: {searched}. "
        "Set TRACECTRL_OPENCLAW_PATH or pass an explicit path."
    )


def list_agents(root: Path) -> list[str]:
    """Return agent IDs discovered under ``<root>/agents/``."""
    agents_dir = root / "agents"
    if not agents_dir.is_dir():
        return []
    return sorted(
        entry.name
        for entry in agents_dir.iterdir()
        if entry.is_dir()
    )


def list_plugins(root: Path) -> list[str]:
    """Return plugin IDs discovered under ``<root>/extensions/``."""
    extensions_dir = root / "extensions"
    if not extensions_dir.is_dir():
        return []
    return sorted(
        entry.name
        for entry in extensions_dir.iterdir()
        if entry.is_dir()
    )


def list_skills(root: Path) -> list[str]:
    """Return skill IDs discovered under ``<root>/skills/``."""
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(
        entry.name
        for entry in skills_dir.iterdir()
        if entry.is_dir()
    )
