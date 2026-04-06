"""Re-export the TUI app for the CLI entry point.

When installed via pip, the setup TUI is accessible as:
    from tracectrl._tui import TraceCtrlApp

The actual TUI code lives in setup/tui.py at the repo root.
This module imports and re-exports it for pip-installed usage.
"""

# Try importing from the repo's setup directory first (dev mode),
# then fall back to a bundled copy if one exists.
import importlib.util
import sys
from pathlib import Path


def _load_from_repo():
    """Try to load tui.py from the repo's setup/ directory."""
    # Walk up from this file to find the repo root
    current = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = current / "setup" / "tui.py"
        if candidate.exists():
            spec = importlib.util.spec_from_file_location("_tui_impl", candidate)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod
        current = current.parent
    return None


_mod = _load_from_repo()
if _mod and hasattr(_mod, "TraceCtrlApp"):
    TraceCtrlApp = _mod.TraceCtrlApp
elif _mod and hasattr(_mod, "TraceCtrlSetup"):
    TraceCtrlApp = _mod.TraceCtrlSetup
else:
    # Provide a helpful error if the TUI can't be found
    class TraceCtrlApp:
        def run(self):
            print("Could not find the TUI setup wizard.")
            print("If running from source, use: python setup/tui.py")
            sys.exit(1)
