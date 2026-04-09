"""TraceCtrl CLI — entry point for setup, diagnostics, and management.

Usage:
    tracectrl setup          Launch the interactive TUI setup wizard
    tracectrl version        Print version and exit
    tracectrl doctor         Check if all services are running
    tracectrl scan [path]    Run an OpenClaw security scan
    tracectrl fix            Apply recommended remediations
    tracectrl monitor        Start the live monitoring dashboard
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def cmd_setup(args: argparse.Namespace) -> None:
    """Launch the interactive TUI setup wizard."""
    try:
        from textual.app import App  # noqa: F401
    except ImportError:
        print(
            "The setup wizard requires additional dependencies.\n"
            "Install them with:\n\n"
            "  pip install tracectrl[setup]\n"
        )
        sys.exit(1)

    # Import and run the TUI — it lives in the setup/ directory at repo root,
    # but when installed via pip, we bundle it as tracectrl._tui
    try:
        from tracectrl._tui import TraceCtrlApp
        app = TraceCtrlApp()
        app.run()
    except ImportError:
        # Fallback: try running the standalone setup/tui.py if we're in the repo
        import subprocess

        tui_path = Path(__file__).resolve().parents[4] / "setup" / "tui.py"
        if tui_path.exists():
            subprocess.run([sys.executable, str(tui_path)], check=True)
        else:
            print(
                "Could not find the setup wizard.\n"
                "If running from source, use: python setup/tui.py\n"
                "If installed via pip, ensure tracectrl[setup] is installed."
            )
            sys.exit(1)


def cmd_version(args: argparse.Namespace) -> None:
    """Print version."""
    from importlib.metadata import version
    try:
        v = version("tracectrl")
    except Exception:
        v = "0.1.0 (dev)"
    print(f"tracectrl {v}")


def cmd_doctor(args: argparse.Namespace) -> None:
    """Check if TraceCtrl services are reachable."""
    import urllib.request
    import urllib.error

    checks = [
        ("Engine API", "http://localhost:8000/api/v1/health"),
        ("Dashboard UI", "http://localhost:3000"),
        ("OTel Collector (HTTP)", "http://localhost:4318/v1/traces"),
    ]

    print("TraceCtrl Doctor\n")
    all_ok = True
    for name, url in checks:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3):
                pass
            print(f"  [OK]   {name} ({url})")
        except urllib.error.HTTPError as e:
            # 405 = endpoint exists but doesn't accept GET (e.g. OTel collector)
            if e.code == 405:
                print(f"  [OK]   {name} ({url})")
            else:
                print(f"  [WARN] {name} — HTTP {e.code} ({url})")
                all_ok = False
        except Exception as e:
            print(f"  [FAIL] {name} — {e} ({url})")
            all_ok = False

    print()
    if all_ok:
        print("All services are running.")
    else:
        print("Some services are not reachable. Run 'docker compose up -d' to start them.")
    sys.exit(0 if all_ok else 1)


def cmd_scan(args: argparse.Namespace) -> None:
    """Run an OpenClaw security scan."""
    import dataclasses

    try:
        from tracectrl_scanner.discovery import discover, list_agents
        from tracectrl_scanner.parser import parse_config
        from tracectrl_scanner.benchmark.runner import run_all
        from tracectrl_scanner.topology.builder import build
        from tracectrl_scanner.topology.risk import score_compound_risks
    except ImportError:
        print(
            "The scan command requires the tracectrl-scanner package.\n"
            "Install it with:\n\n"
            "  pip install tracectrl-scanner\n"
        )
        sys.exit(1)

    path = Path(args.path) if args.path else None
    profile = args.profile

    # --- Discovery & parsing ---------------------------------------------------
    root = discover(path)
    config = parse_config(root)
    agent_ids = list_agents(root)

    # --- Benchmark & topology --------------------------------------------------
    results = run_all(config, root)
    graph = build(config, root, agent_ids)
    compound = score_compound_risks(results, graph)

    # --- Severity summary ------------------------------------------------------
    severity_counts = Counter(r.severity.value if hasattr(r.severity, 'value') else r.severity for r in results)
    summary = {
        "critical": severity_counts.get("CRITICAL", 0),
        "high": severity_counts.get("HIGH", 0),
        "medium": severity_counts.get("MEDIUM", 0),
        "pass": severity_counts.get("PASS", 0),
    }

    has_critical = summary["critical"] > 0

    # --- JSON output -----------------------------------------------------------
    if args.json:
        payload = {
            "scan_path": str(root),
            "profile": profile,
            "checks": [dataclasses.asdict(r) for r in results],
            "compound_risks": compound,
            "topology": {
                "nodes": len(graph.nodes),
                "edges": len(graph.edges),
            },
            "summary": summary,
        }
        print(json.dumps(payload, indent=2, default=str))
        sys.exit(1 if has_critical else 0)

    # --- Rich terminal report --------------------------------------------------
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
    except ImportError:
        print(
            "Rich terminal output requires the 'rich' package.\n"
            "Install it with:\n\n"
            "  pip install rich\n\n"
            "Or use --json for plain output."
        )
        sys.exit(1)

    console = Console()

    # Header panel
    header = (
        f"  [bold]TraceCtrl — OpenClaw Security Scan[/bold]\n"
        f"  Path: {root}   Profile: {profile}"
    )
    console.print(Panel(header, expand=True))
    console.print()

    # Severity summary line
    sev_line = (
        f"  [bold red]CRITICAL[/bold red]  {summary['critical']}    "
        f"[bold yellow]HIGH[/bold yellow]  {summary['high']}    "
        f"[bold cyan]MEDIUM[/bold cyan]  {summary['medium']}    "
        f"[bold green]PASS[/bold green]  {summary['pass']}"
    )
    console.print(sev_line)
    console.print()

    # Findings table (non-PASS only)
    sev_val = lambda r: r.severity.value if hasattr(r.severity, 'value') else r.severity  # noqa: E731
    findings = [r for r in results if sev_val(r) != "PASS"]
    if findings:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Check ID", style="dim", min_width=14)
        table.add_column("Severity", min_width=10)
        table.add_column("Finding", min_width=34)

        severity_style = {
            "CRITICAL": "bold red",
            "HIGH": "bold yellow",
            "MEDIUM": "bold cyan",
        }

        for r in findings:
            sv = sev_val(r)
            style = severity_style.get(sv, "")
            table.add_row(r.check_id, f"[{style}]{sv}[/{style}]", r.finding or "")

        console.print(table)
        console.print()

    # Compound risk signals
    if compound:
        console.print("  [bold]Compound Risk Signals[/bold]")
        console.rule(style="dim")
        for c in compound:
            sev = c.get("severity", "HIGH")
            cid = c.get("id", "")
            desc = c.get("description", "")
            style = severity_style.get(sev, "")
            console.print(f"  [{style}][{sev}][/{style}] {cid} {desc}")
        console.print()

    # Topology summary
    console.print(
        f"  Topology: {len(graph.nodes)} nodes · {len(graph.edges)} edges"
    )
    console.print()

    # Remediation hint
    console.print("  Run [bold]tracectrl fix --auto[/bold] to remediate.")
    console.print()

    sys.exit(1 if has_critical else 0)


def cmd_fix(args: argparse.Namespace) -> None:
    """Apply automated remediations from the last scan."""
    try:
        from tracectrl_scanner.discovery import discover
        from tracectrl_scanner.parser import parse_config
        from tracectrl_scanner.benchmark.runner import run_all
        from tracectrl_scanner.fix import get_automatable_fixes, apply_fixes, print_fix_report
    except ImportError:
        print("Scanner not installed. Run: pip install tracectrl-scanner")
        sys.exit(1)

    from rich.console import Console
    console = Console()

    path = getattr(args, 'path', None)
    auto = getattr(args, 'auto', False)
    dry_run = getattr(args, 'dry_run', False)

    try:
        root = discover(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    config_path = root / "openclaw.json"
    config = parse_config(root)
    results = run_all(config, root)
    automatable, manual = get_automatable_fixes(results)

    if not automatable and not manual:
        console.print("[green]No findings to fix — all checks pass![/green]")
        sys.exit(0)

    if dry_run:
        console.print("[bold]Dry run — showing what would be fixed:[/bold]\n")
        applied = apply_fixes(config, config_path, automatable, dry_run=True)
        print_fix_report(applied, manual)
        sys.exit(0)

    if not auto:
        console.print(f"[bold]{len(automatable)} automated fixes available, {len(manual)} require manual action.[/bold]")
        console.print("Run with --auto to apply, or --dry-run to preview.\n")
        print_fix_report([], manual)
        sys.exit(0)

    # Apply fixes
    applied = apply_fixes(config, config_path, automatable)
    print_fix_report(applied, manual)

    # Re-scan
    console.print("\n[bold]Re-scanning after fixes...[/bold]")
    new_config = parse_config(root)
    new_results = run_all(new_config, root)
    new_failed = [r for r in new_results if not r.passed]
    old_failed = [r for r in results if not r.passed]
    console.print(f"\n  Before: {len(old_failed)} findings → After: {len(new_failed)} findings")
    if not new_failed:
        console.print("  [bold green]All automated fixes verified — clean scan![/bold green]")
    sys.exit(0)


def cmd_monitor(args: argparse.Namespace) -> None:
    """Start the live monitoring dashboard (not yet implemented)."""
    print("The monitor command is not yet implemented.")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="tracectrl",
        description="TraceCtrl — Security observability for agentic AI",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- setup -----------------------------------------------------------------
    subparsers.add_parser("setup", help="Launch the interactive setup wizard")

    # --- version ---------------------------------------------------------------
    subparsers.add_parser("version", help="Print version and exit")

    # --- doctor ----------------------------------------------------------------
    subparsers.add_parser("doctor", help="Check if all services are running")

    # --- scan ------------------------------------------------------------------
    scan_parser = subparsers.add_parser(
        "scan", help="Run an OpenClaw security scan"
    )
    scan_parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to scan (auto-discovers if omitted)",
    )
    scan_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results as machine-readable JSON",
    )
    scan_parser.add_argument(
        "--profile",
        choices=["L1", "L2"],
        default="L1",
        help="Scan profile level (default: L1)",
    )

    # --- fix -------------------------------------------------------------------
    fix_parser = subparsers.add_parser(
        "fix", help="Apply recommended remediations"
    )
    fix_parser.add_argument(
        "--auto",
        action="store_true",
        default=False,
        help="Automatically apply all safe remediations",
    )
    fix_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be changed without applying",
    )
    fix_parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to OpenClaw installation (default: auto-discover)",
    )

    # --- monitor ---------------------------------------------------------------
    monitor_parser = subparsers.add_parser(
        "monitor", help="Start the live monitoring dashboard"
    )
    monitor_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for the monitoring dashboard",
    )

    args = parser.parse_args()

    commands = {
        "setup": cmd_setup,
        "version": cmd_version,
        "doctor": cmd_doctor,
        "scan": cmd_scan,
        "fix": cmd_fix,
        "monitor": cmd_monitor,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
