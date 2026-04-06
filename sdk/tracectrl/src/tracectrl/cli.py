"""TraceCtrl CLI — entry point for setup, diagnostics, and management.

Usage:
    tracectrl setup          Launch the interactive TUI setup wizard
    tracectrl version        Print version and exit
    tracectrl doctor         Check if all services are running
"""

import argparse
import sys


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
        from pathlib import Path

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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="tracectrl",
        description="TraceCtrl — Security observability for agentic AI",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("setup", help="Launch the interactive setup wizard")
    subparsers.add_parser("version", help="Print version and exit")
    subparsers.add_parser("doctor", help="Check if all services are running")

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "version":
        cmd_version(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
