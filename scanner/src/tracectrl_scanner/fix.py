"""Automated remediation for OpenClaw security findings."""

import shutil
from pathlib import Path
from typing import Any
from rich.console import Console
from .benchmark.models import CheckResult

console = Console()

# Map of check_id → fix function
# Each fix function takes the config dict and mutates it in place
AUTOMATED_FIXES: dict[str, callable] = {}

def _register(check_id: str):
    """Decorator to register a fix function for a check ID."""
    def decorator(fn):
        AUTOMATED_FIXES[check_id] = fn
        return fn
    return decorator

@_register("OC-NET-001")
def fix_net_001(config: dict[str, Any]) -> str:
    """Set gateway.bind to loopback"""
    gateway = config.get("gateway")
    if isinstance(gateway, dict):
        gateway["bind"] = "loopback"
    else:
        config["gateway"] = {"bind": "loopback"}
    return 'Set gateway.bind = "loopback"'

@_register("OC-TOOL-001")
def fix_tool_001(config: dict[str, Any]) -> str:
    """Remove bash and exec from tools.allow/deny lists"""
    removed = []
    dangerous = ("bash", "exec")

    # Only modify sections that already exist — never create empty ones
    # Check agents.defaults.tools.allow
    agent_tools = (config.get("agents", {}).get("defaults", {})
                   .get("tools", {}).get("allow"))
    if isinstance(agent_tools, list):
        for d in dangerous:
            while d in agent_tools:
                agent_tools.remove(d)
                removed.append(d)

    # Check top-level tools.allow
    top_tools = config.get("tools", {}).get("allow")
    if isinstance(top_tools, list):
        for d in dangerous:
            while d in top_tools:
                top_tools.remove(d)
                removed.append(d)

    # Check per-agent tool lists
    for agent in config.get("agents", {}).get("list", []):
        if isinstance(agent, dict):
            per_agent = agent.get("tools", {}).get("allow")
            if isinstance(per_agent, list):
                for d in dangerous:
                    while d in per_agent:
                        per_agent.remove(d)
                        removed.append(f"{d} (agent: {agent.get('id', '?')})")

    return f'Removed {", ".join(removed)} from tools.allow' if removed else 'No dangerous tools found in allow lists'

@_register("OC-TOOL-002")
def fix_tool_002(config: dict[str, Any]) -> str:
    """Remove wildcard from tools.allow"""
    removed = False

    # Only modify existing sections
    agent_tools = (config.get("agents", {}).get("defaults", {})
                   .get("tools", {}).get("allow"))
    if isinstance(agent_tools, list):
        while "*" in agent_tools:
            agent_tools.remove("*")
            removed = True

    top_tools = config.get("tools", {}).get("allow")
    if isinstance(top_tools, list):
        while "*" in top_tools:
            top_tools.remove("*")
            removed = True

    for agent in config.get("agents", {}).get("list", []):
        if isinstance(agent, dict):
            per_agent = agent.get("tools", {}).get("allow")
            if isinstance(per_agent, list):
                while "*" in per_agent:
                    per_agent.remove("*")
                    removed = True

    return 'Removed "*" from tools.allow — add specific tools you need' if removed else 'No wildcard found'

@_register("OC-ING-001")
def fix_ing_001(config: dict[str, Any]) -> str:
    """Set dmPolicy to contacts_only for open channels"""
    fixed = []
    channels = config.get("channels", {})
    for name, cfg in channels.items():
        if isinstance(cfg, dict) and cfg.get("dmPolicy") == "open":
            cfg["dmPolicy"] = "pairing"
            fixed.append(name)
    return f'Set dmPolicy = "pairing" for: {", ".join(fixed)}' if fixed else 'No open channels found'

@_register("OC-PERS-001")
def fix_pers_001(config: dict[str, Any]) -> str:
    """Disable cron"""
    cron = config.get("cron")
    if isinstance(cron, dict):
        cron["enabled"] = False
    else:
        config["cron"] = {"enabled": False}
    return 'Set cron.enabled = false'

# OC-LOG-001 (audit logging) is NOT auto-fixable — logging.audit may not be
# a valid schema key in OpenClaw's strict Zod validation. Kept as manual.

@_register("OC-LOG-002")
def fix_log_002(config: dict[str, Any]) -> str:
    """Set log level to info if debug"""
    logging_cfg = config.get("logging")
    if isinstance(logging_cfg, dict) and logging_cfg.get("level") == "debug":
        logging_cfg["level"] = "info"
        return 'Set logging.level = "info" (was "debug")'
    return 'Log level already not debug'


def get_automatable_fixes(results: list[CheckResult]) -> tuple[list[CheckResult], list[CheckResult]]:
    """Split results into automatable and manual-only failures."""
    failed = [r for r in results if not r.passed]
    automatable = [r for r in failed if r.check_id in AUTOMATED_FIXES]
    manual = [r for r in failed if r.check_id not in AUTOMATED_FIXES]
    return automatable, manual


def apply_fixes(
    config: dict[str, Any],
    config_path: Path,
    automatable: list[CheckResult],
    dry_run: bool = False,
) -> list[dict]:
    """Apply automated fixes. Returns list of {check_id, description} for each fix applied."""
    applied = []

    if dry_run:
        for r in automatable:
            applied.append({
                "check_id": r.check_id,
                "description": f"[DRY RUN] Would fix: {r.title}",
            })
        return applied

    # Create backup
    backup_path = config_path.with_suffix(".json.bak")
    shutil.copy2(config_path, backup_path)
    console.print(f"[dim]Backup saved to {backup_path}[/dim]")

    # Apply each fix
    for r in automatable:
        fix_fn = AUTOMATED_FIXES[r.check_id]
        description = fix_fn(config)
        applied.append({
            "check_id": r.check_id,
            "description": description,
        })

    # Write updated config — prefer pyjson5 to preserve JSON5 compatibility,
    # fall back to stdlib json (which strips comments)
    try:
        import pyjson5
        with open(config_path, "w") as f:
            f.write(pyjson5.dumps(config, indent=2))
    except ImportError:
        import json
        console.print("[yellow]Note: Comments in openclaw.json will be removed during rewrite.[/yellow]")
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

    return applied


def print_fix_report(applied: list[dict], manual: list[CheckResult]) -> None:
    """Print a summary of fixes applied and manual actions needed."""
    if applied:
        console.print("\n[bold green]Automated Fixes Applied[/bold green]")
        for fix in applied:
            console.print(f"  [green]✓[/green] {fix['check_id']}: {fix['description']}")

    if manual:
        console.print("\n[bold yellow]Manual Actions Required[/bold yellow]")
        for r in manual:
            console.print(f"  [yellow]![/yellow] {r.check_id}: {r.title}")
            console.print(f"    [dim]{r.remediation}[/dim]")
