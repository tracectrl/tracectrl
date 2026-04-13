"""TraceCtrl TUI — first-time setup wizard."""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from textual.app import App, ComposeResult
    from textual.screen import Screen
    from textual.widgets import (
        Button, Input, Label, Static, RichLog, Select, DataTable,
        LoadingIndicator,
    )
    from textual.containers import Horizontal, Vertical
    from textual.binding import Binding
    from textual import work
    from textual.worker import Worker
    from rich.text import Text
    # Textual 8.0 renamed Select.BLANK to Select.NULL
    SELECT_BLANK = getattr(Select, 'BLANK', None) or getattr(Select, 'NULL', None)
except ImportError:
    print("Textual not installed. Run: pip install textual rich")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER_URL = os.environ.get("TRACECTRL_REGISTER_URL", "https://tracectrl.ai/api/register")
REGISTERED_FLAG = Path.home() / ".tracectrl_registered"

SEVERITY_COLORS = {
    "CRITICAL": "#FF4D4D",
    "HIGH": "#FF6B35",
    "MEDIUM": "#FFBB00",
    "PASS": "#00CC66",
    "MANUAL": "#8A8A8A",
}

CATEGORY_KEYWORDS = {
    "Security": ["network", "credentials", "tools", "ingress", "guardrails",
                 "filesystem", "lateral_movement", "plugins", "llm_providers",
                 "security_advanced"],
    "Operational": ["operational", "logging"],
    "Performance": ["performance"],
    "Compliance": ["compliance", "persistence"],
}


@dataclass
class WizardState:
    email: str = ""
    user_type: str = ""
    org_size: str = ""
    role: str = ""
    framework: str = ""
    openclaw_path: Optional[Path] = None
    scan_results: list = field(default_factory=list)
    scan_root: Optional[Path] = None
    project_name: str = "my-agent-service"
    dashboard_url: str = "http://localhost:3000"


def _classify_category(section: str) -> str:
    """Map a check's section field to a UI category."""
    lower = section.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return cat
    return "Security"


# ---------------------------------------------------------------------------
# Screen 1: Welcome
# ---------------------------------------------------------------------------

class WelcomeScreen(Screen):
    """Screen 1: Welcome."""

    def compose(self) -> ComposeResult:
        yield Static(
            "\n\n"
            "  ████████╗██████╗  █████╗  ██████╗███████╗ ██████╗████████╗██████╗ ██╗\n"
            "  ╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██╔════╝██╔════╝╚══██╔══╝██╔══██╗██║\n"
            "     ██║   ██████╔╝███████║██║     █████╗  ██║        ██║   ██████╔╝██║\n"
            "     ██║   ██╔══██╗██╔══██║██║     ██╔══╝  ██║        ██║   ██╔══██╗██║\n"
            "     ██║   ██║  ██║██║  ██║╚██████╗███████╗╚██████╗   ██║   ██║  ██║███████╗\n"
            "     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝\n"
            "\n"
            "  Agentic AI Security Observability\n"
            "  Let's get you set up in 2 minutes.\n\n",
            id="welcome-art",
        )
        yield Button("Get Started →", id="btn-start", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-start":
            # Show registration if not already registered
            if REGISTERED_FLAG.exists():
                self.app.push_screen(FrameworkScreen(self.app.state))
            else:
                self.app.push_screen(RegistrationScreen())


# ---------------------------------------------------------------------------
# Screen 1.5: Registration
# ---------------------------------------------------------------------------

class RegistrationScreen(Screen):
    """Screen 1.5: Registration — collects user info to improve TraceCtrl."""

    USER_TYPES = [
        ("Hobbyist", "hobbyist"),
        ("Individual Developer", "individual"),
        ("Enterprise Developer", "enterprise"),
    ]

    ORG_SIZES = [
        ("1–10", "1-10"),
        ("11–50", "11-50"),
        ("51–200", "51-200"),
        ("201–1000", "201-1000"),
        ("1000+", "1000+"),
    ]

    ROLES = [
        ("Engineer", "engineer"),
        ("Security", "security"),
        ("DevOps / Platform", "devops"),
        ("Engineering Manager", "manager"),
        ("CISO / VP", "ciso"),
        ("Other", "other"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("\n  Quick Registration\n", id="reg-title")
        yield Static(
            "  Help us build what you need. We won't spam you.\n"
            "  Privacy policy: https://tracectrl.ai/privacy\n",
            id="reg-subtitle",
        )

        yield Label("Email *")
        yield Input(placeholder="you@company.com", id="reg_email")

        yield Label("I am a...")
        yield Select(
            [(label, value) for label, value in self.USER_TYPES],
            id="reg_user_type",
            prompt="Select user type",
        )

        yield Label("Organization Size")
        yield Select(
            [(label, value) for label, value in self.ORG_SIZES],
            id="reg_org_size",
            prompt="Select size (enterprise only)",
        )

        yield Label("Role")
        yield Select(
            [(label, value) for label, value in self.ROLES],
            id="reg_role",
            prompt="Select your role",
        )

        yield Static("")
        yield Horizontal(
            Button("Skip for now", id="btn-skip"),
            Button("Register & Continue →", id="btn-register", variant="primary"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-skip":
            self.app.push_screen(FrameworkScreen(self.app.state))
        elif event.button.id == "btn-register":
            self._submit_registration()

    def _submit_registration(self) -> None:
        email = self.query_one("#reg_email", Input).value.strip()
        user_type_sel = self.query_one("#reg_user_type", Select)
        role_sel = self.query_one("#reg_role", Select)
        org_size_sel = self.query_one("#reg_org_size", Select)

        user_type = str(user_type_sel.value) if user_type_sel.value != SELECT_BLANK else ""
        role = str(role_sel.value) if role_sel.value != SELECT_BLANK else ""
        org_size = str(org_size_sel.value) if org_size_sel.value != SELECT_BLANK else None

        if not email or "@" not in email:
            self.notify("Please enter a valid email address", severity="error")
            return

        if not user_type:
            self.notify("Please select a user type", severity="error")
            return

        if not role:
            self.notify("Please select your role", severity="error")
            return

        # Store in state
        state = self.app.state
        state.email = email
        state.user_type = user_type
        state.role = role
        state.org_size = org_size or ""

        # Get version
        try:
            from importlib.metadata import version
            ver = version("tracectrl")
        except Exception:
            ver = "0.1.0"

        payload = {
            "email": email,
            "user_type": user_type,
            "org_size": org_size,
            "role": role,
            "version": ver,
            "source": "tui",
        }

        # POST to registration endpoint (non-blocking, don't fail setup on error)
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                REGISTER_URL,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # Silently continue — don't block setup on registration failure

        # Mark as registered
        try:
            REGISTERED_FLAG.touch()
        except Exception:
            pass

        self.notify("Thanks for registering!", severity="information")
        self.app.push_screen(FrameworkScreen(self.app.state))


# ---------------------------------------------------------------------------
# Screen 2: Framework choice
# ---------------------------------------------------------------------------

class FrameworkScreen(Screen):
    """Choose between OpenClaw and Strands agent frameworks."""

    def __init__(self, state: WizardState):
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        yield Static("\n  Choose Your Agent Framework\n", id="framework-title")
        yield Static(
            "  TraceCtrl supports multiple agent frameworks.\n"
            "  Select the one you're using to tailor the setup experience.\n",
            id="framework-subtitle",
        )
        yield Vertical(
            Button("OpenClaw", id="btn-openclaw", variant="primary"),
            Button("Strands (AWS Bedrock)", id="btn-strands", variant="primary"),
            id="framework-buttons",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-openclaw":
            self.state.framework = "openclaw"
            self.app.push_screen(OpenClawPathScreen(self.state))
        elif event.button.id == "btn-strands":
            self.state.framework = "strands"
            self.app.push_screen(StrandsActionScreen(self.state))


# ---------------------------------------------------------------------------
# Screen 3a: OpenClaw path input
# ---------------------------------------------------------------------------

class OpenClawPathScreen(Screen):
    """Input and validate the OpenClaw installation path."""

    def __init__(self, state: WizardState):
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        yield Static("\n  OpenClaw Installation Path\n", id="ocpath-title")
        yield Static(
            "  Point us at your OpenClaw directory so we can scan its configuration.\n",
            id="ocpath-subtitle",
        )
        yield Label("Path to OpenClaw root")
        yield Input(value="~/.openclaw/", id="ocpath-input", placeholder="~/.openclaw/")
        yield Static("", id="ocpath-status")
        yield Static("")
        yield Horizontal(
            Button("← Back", id="btn-back"),
            Button("Next →", id="btn-next", variant="primary", disabled=True),
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "ocpath-input":
            return
        raw = event.value.strip()
        status_widget = self.query_one("#ocpath-status", Static)
        next_btn = self.query_one("#btn-next", Button)

        if not raw:
            status_widget.update("  Enter a path to continue")
            next_btn.disabled = True
            return

        expanded = Path(raw).expanduser().resolve()
        if not expanded.is_dir():
            status_widget.update("  [#FF4D4D]✗[/] Directory does not exist")
            next_btn.disabled = True
            return

        config_file = expanded / "openclaw.json"
        if not config_file.is_file():
            status_widget.update(
                f"  [#FFBB00]⚠[/] Directory exists but openclaw.json not found"
            )
            next_btn.disabled = True
            return

        status_widget.update(f"  [#00CC66]✓[/] Found openclaw.json at {expanded}")
        self.state.openclaw_path = expanded
        next_btn.disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-next":
            self.app.push_screen(OpenClawActionScreen(self.state))


# ---------------------------------------------------------------------------
# Screen 3b: OpenClaw action choice
# ---------------------------------------------------------------------------

class OpenClawActionScreen(Screen):
    """Choose to scan OpenClaw or skip directly to trace exploration."""

    def __init__(self, state: WizardState):
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        yield Static("\n  OpenClaw Setup\n", id="ocaction-title")
        yield Static(
            f"  Validated path: {self.state.openclaw_path}\n",
            id="ocaction-path",
        )
        yield Static(
            "  You can scan your OpenClaw configuration for security issues,\n"
            "  or skip ahead to explore traces in the dashboard.\n",
            id="ocaction-subtitle",
        )
        yield Vertical(
            Button("Scan OpenClaw", id="btn-scan", variant="primary"),
            Button("Run & Explore Traces →", id="btn-explore", variant="primary"),
            id="ocaction-buttons",
        )
        yield Static("")
        yield Button("← Back", id="btn-back")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-scan":
            self.app.push_screen(ScanScreen(self.state))
        elif event.button.id == "btn-explore":
            self.app.push_screen(ProjectScreen(self.state))


# ---------------------------------------------------------------------------
# Screen 4: Scanner
# ---------------------------------------------------------------------------

class ScanScreen(Screen):
    """Run the TraceCtrl scanner against OpenClaw and display results."""

    def __init__(self, state: WizardState):
        super().__init__()
        self.state = state
        self._active_filter = "All"

    def compose(self) -> ComposeResult:
        yield Static("\n  OpenClaw Security Scan\n", id="scan-title")
        yield Static("", id="scan-summary")
        yield LoadingIndicator(id="scan-loading")
        yield Horizontal(
            Button("All", id="tab-all", variant="primary"),
            Button("Security", id="tab-security"),
            Button("Operational", id="tab-operational"),
            Button("Performance", id="tab-performance"),
            Button("Compliance", id="tab-compliance"),
            id="scan-tabs",
        )
        yield DataTable(id="scan-table", cursor_type="row", zebra_stripes=True)
        yield RichLog(id="scan-fix-log", highlight=True, markup=True)
        yield Static(
            "  Results also accessible at web UI after setup.\n",
            id="scan-note",
        )
        yield Horizontal(
            Button("← Back", id="btn-back"),
            Button("Fix & Rescan", id="btn-fix", variant="warning", disabled=True),
            Button("Continue to Setup →", id="btn-continue", variant="primary", disabled=True),
            id="scan-actions",
        )

    def on_mount(self) -> None:
        table = self.query_one("#scan-table", DataTable)
        table.add_columns("Check ID", "Severity", "Category", "Finding")
        # Hide elements initially
        self.query_one("#scan-tabs").display = False
        self.query_one("#scan-table").display = False
        self.query_one("#scan-fix-log").display = False
        self.query_one("#scan-note").display = False
        self._run_scan()

    @work(thread=True, exclusive=True)
    def _run_scan(self) -> None:
        try:
            from tracectrl_scanner.discovery import discover
            from tracectrl_scanner.parser import parse_config
            from tracectrl_scanner.benchmark.runner import run_all

            root = discover(self.state.openclaw_path)
            config = parse_config(root)
            results = run_all(config, root)
            self.state.scan_results = results
            self.state.scan_root = root
            self.app.call_from_thread(self._show_results, results)
        except Exception as e:
            self.app.call_from_thread(self._show_scan_error, str(e))

    def _show_scan_error(self, message: str) -> None:
        self.query_one("#scan-loading").display = False
        self.notify(f"Scan failed: {message}", severity="error")

    def _show_results(self, results: list) -> None:
        # Hide loading
        self.query_one("#scan-loading").display = False
        # Show results UI
        self.query_one("#scan-tabs").display = True
        self.query_one("#scan-table").display = True
        self.query_one("#scan-note").display = True

        # Build summary
        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "PASS": 0, "MANUAL": 0}
        for r in results:
            counts[r.severity.value] = counts.get(r.severity.value, 0) + 1

        summary_parts = []
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "PASS"]:
            color = SEVERITY_COLORS[sev]
            summary_parts.append(f"[{color}]{sev} {counts[sev]}[/]")
        summary_line = "  " + "  |  ".join(summary_parts)
        self.query_one("#scan-summary", Static).update(summary_line)

        # Enable buttons
        has_failures = any(not r.passed for r in results)
        self.query_one("#btn-fix", Button).disabled = not has_failures
        self.query_one("#btn-continue", Button).disabled = False

        # Populate table
        self._populate_table(results)

    def _populate_table(self, results: list, category_filter: str = "All") -> None:
        table = self.query_one("#scan-table", DataTable)
        table.clear()
        for r in results:
            cat = _classify_category(r.section)
            if category_filter != "All" and cat != category_filter:
                continue
            sev_color = SEVERITY_COLORS.get(r.severity.value, "#F5F5F5")
            sev_text = Text(r.severity.value, style=sev_color)
            finding_text = r.finding or ("PASS" if r.passed else r.title)
            table.add_row(
                r.check_id,
                sev_text,
                cat,
                finding_text,
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        if btn_id == "btn-back":
            self.app.pop_screen()
            return

        if btn_id == "btn-continue":
            self.app.push_screen(ProjectScreen(self.state))
            return

        if btn_id == "btn-fix":
            self.query_one("#scan-fix-log").display = True
            self.query_one("#scan-loading").display = True
            self.query_one("#btn-fix", Button).disabled = True
            self._run_fix_rescan()
            return

        # Tab buttons
        tab_map = {
            "tab-all": "All",
            "tab-security": "Security",
            "tab-operational": "Operational",
            "tab-performance": "Performance",
            "tab-compliance": "Compliance",
        }
        if btn_id in tab_map:
            self._active_filter = tab_map[btn_id]
            # Update tab button styles
            for tid, _ in tab_map.items():
                btn = self.query_one(f"#{tid}", Button)
                btn.variant = "primary" if tid == btn_id else "default"
            self._populate_table(self.state.scan_results, self._active_filter)

    @work(thread=True, exclusive=True)
    def _run_fix_rescan(self) -> None:
        try:
            from tracectrl_scanner.parser import parse_config
            from tracectrl_scanner.benchmark.runner import run_all
            from tracectrl_scanner.fix import get_automatable_fixes, apply_fixes

            config_path = self.state.scan_root / "openclaw.json"
            config = parse_config(self.state.scan_root)
            automatable, manual = get_automatable_fixes(self.state.scan_results)
            applied = apply_fixes(config, config_path, automatable)

            for fix in applied:
                self.app.call_from_thread(
                    self._log_fix,
                    f"[#00CC66]✓[/] {fix['check_id']}: {fix['description']}",
                )

            if manual:
                self.app.call_from_thread(
                    self._log_fix,
                    f"[#FFBB00]![/] {len(manual)} finding(s) require manual remediation",
                )

            new_config = parse_config(self.state.scan_root)
            new_results = run_all(new_config, self.state.scan_root)
            self.state.scan_results = new_results
            self.app.call_from_thread(self._show_results, new_results)
        except Exception as e:
            self.app.call_from_thread(self._show_scan_error, str(e))

    def _log_fix(self, message: str) -> None:
        log = self.query_one("#scan-fix-log", RichLog)
        log.write(message)


# ---------------------------------------------------------------------------
# Screen 3s: Strands action
# ---------------------------------------------------------------------------

class StrandsActionScreen(Screen):
    """Strands framework — skip to trace exploration."""

    def __init__(self, state: WizardState):
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        yield Static("\n  Strands Agent Framework\n", id="strands-title")
        yield Static(
            "  Strands (AWS Bedrock) agents emit OpenTelemetry traces that TraceCtrl\n"
            "  can ingest and visualize. Set up the TraceCtrl stack and point your\n"
            "  Strands agent's OTel exporter at the collector endpoint.\n",
            id="strands-subtitle",
        )
        yield Static(
            "  After setup you'll have:\n"
            "    - A ClickHouse database for trace storage\n"
            "    - The TraceCtrl engine for risk scoring and analytics\n"
            "    - A dashboard at http://localhost:3000\n"
            "    - An OTel collector on port 4318 (HTTP) / 4317 (gRPC)\n",
            id="strands-info",
        )
        yield Static("")
        yield Horizontal(
            Button("← Back", id="btn-back"),
            Button("Run & Explore Traces →", id="btn-explore", variant="primary"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-explore":
            self.app.push_screen(ProjectScreen(self.state))


# ---------------------------------------------------------------------------
# Screen 5: Project name & .env
# ---------------------------------------------------------------------------

class ProjectScreen(Screen):
    """Name the project and preview what will be written."""

    def __init__(self, state: WizardState):
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        yield Static("\n  Name Your Project\n", id="project-title")
        yield Label("Project / service name")
        yield Input(
            value=self.state.project_name,
            id="project-name-input",
            placeholder="my-agent-service",
        )
        yield Static(
            "\n  This will:\n"
            "    1. Write a .env file with your project settings\n"
            "    2. Start 4 Docker services:\n"
            "       - ClickHouse  (trace storage)\n"
            "       - TraceCtrl Engine  (risk scoring API)\n"
            "       - TraceCtrl UI  (dashboard)\n"
            "       - OTel Collector  (trace ingestion)\n",
            id="project-preview",
        )
        yield Static("")
        yield Horizontal(
            Button("← Back", id="btn-back"),
            Button("Launch TraceCtrl →", id="btn-launch", variant="primary"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-launch":
            name = self.query_one("#project-name-input", Input).value.strip()
            if not name:
                self.notify("Please enter a project name", severity="error")
                return
            self.state.project_name = name
            try:
                self._write_env()
            except OSError as e:
                self.notify(f"Could not write .env: {e}", severity="error")
                return
            self.app.push_screen(DockerScreen(self.state))

    def _write_env(self) -> None:
        state = self.state
        env_content = (
            f"# Generated by TraceCtrl TUI\n"
            f"TRACECTRL_SERVICE_NAME={state.project_name}\n"
            f"CLICKHOUSE_HOST=clickhouse\n"
            f"CLICKHOUSE_PORT=9000\n"
            f"CLICKHOUSE_DB=tracectrl\n"
            f"PIPELINE_INTERVAL_SECONDS=60\n"
            f"\n"
            f"ENGINE_URL=http://tracectrl-engine:8000\n"
            f"VITE_ENGINE_URL=http://localhost:8000\n"
        )
        env_path = REPO_ROOT / ".env"
        env_path.write_text(env_content)


# ---------------------------------------------------------------------------
# Screen 6: Docker launch
# ---------------------------------------------------------------------------

class DockerScreen(Screen):
    """Launch Docker Compose and poll service health."""

    HEALTH_ENDPOINTS = [
        ("ClickHouse", "http://localhost:8123", "/ping"),
        ("Engine", "http://localhost:8000", "/api/v1/health"),
        ("UI", "http://localhost:3000", "/"),
        ("Collector", "http://localhost:4318", "/v1/traces"),
    ]

    def __init__(self, state: WizardState):
        super().__init__()
        self.state = state
        self._healthy_services: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Static("\n  Launching TraceCtrl\n", id="docker-title")
        yield RichLog(id="docker-log", highlight=True, markup=True)
        yield Static("", id="docker-health")
        yield Button("Open Dashboard →", id="btn-dashboard", variant="primary", disabled=True)
        yield Button("Done — Exit Setup", id="btn-done")

    def on_mount(self) -> None:
        log = self.query_one("#docker-log", RichLog)
        log.write("[bold green]✓[/] .env written successfully")
        log.write(f"[bold]Working directory:[/] {REPO_ROOT}")

        if not shutil.which("docker"):
            log.write(
                "[bold yellow]⚠ Docker not found.[/]\n"
                "  Install Docker and run 'docker compose up -d' manually.\n"
                f"  Then visit {self.state.dashboard_url}"
            )
            self.query_one("#btn-dashboard", Button).disabled = False
            return

        log.write("[bold]Running:[/] docker compose up -d\n")
        self._run_docker()

    @work(thread=True, exclusive=True)
    def _run_docker(self) -> None:
        try:
            proc = subprocess.Popen(
                ["docker", "compose", "up", "-d"],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in proc.stdout:
                self.app.call_from_thread(self._log, line.rstrip())
            proc.wait(timeout=180)

            if proc.returncode == 0:
                self.app.call_from_thread(self._on_compose_success)
            else:
                self.app.call_from_thread(
                    self._log,
                    f"[bold red]✗ docker compose exited with code {proc.returncode}[/]",
                )
        except subprocess.TimeoutExpired:
            self.app.call_from_thread(
                self._log,
                "[bold yellow]⚠ Timeout waiting for docker compose. Check manually.[/]",
            )
        except FileNotFoundError:
            self.app.call_from_thread(
                self._log,
                "[bold yellow]⚠ Docker not found. Install Docker and run 'docker compose up -d' manually.[/]",
            )

    def _log(self, message: str) -> None:
        self.query_one("#docker-log", RichLog).write(message)

    def _on_compose_success(self) -> None:
        self._log("[bold green]✓ Docker Compose started successfully[/]")
        self._log("\n[bold]Polling service health...[/]\n")
        self._poll_health()

    @work(thread=True, exclusive=True)
    def _poll_health(self) -> None:
        max_attempts = 30
        for attempt in range(max_attempts):
            all_healthy = True
            for name, base_url, path in self.HEALTH_ENDPOINTS:
                if name in self._healthy_services:
                    continue
                try:
                    url = f"{base_url}{path}"
                    req = urllib.request.Request(url, method="GET")
                    resp = urllib.request.urlopen(req, timeout=3)
                    if resp.status < 400:
                        self._healthy_services.add(name)
                        self.app.call_from_thread(
                            self._log,
                            f"  [#00CC66]✓[/] {name} is healthy",
                        )
                except urllib.error.HTTPError as e:
                    # 405 = endpoint exists but doesn't accept GET (e.g. OTel collector)
                    if e.code == 405:
                        self._healthy_services.add(name)
                        self.app.call_from_thread(
                            self._log,
                            f"  [#00CC66]✓[/] {name} is healthy",
                        )
                    else:
                        all_healthy = False
                except Exception:
                    all_healthy = False

            self.app.call_from_thread(self._update_health_panel)

            if len(self._healthy_services) == len(self.HEALTH_ENDPOINTS):
                self.app.call_from_thread(self._all_healthy)
                return

            time.sleep(2)

        # Timeout — show partial results
        missing = [
            name for name, _, _ in self.HEALTH_ENDPOINTS
            if name not in self._healthy_services
        ]
        self.app.call_from_thread(
            self._log,
            f"[bold yellow]⚠ Timed out waiting for: {', '.join(missing)}[/]",
        )
        self.app.call_from_thread(self._enable_dashboard)

    def _update_health_panel(self) -> None:
        lines = []
        for name, _, _ in self.HEALTH_ENDPOINTS:
            if name in self._healthy_services:
                lines.append(f"  [#00CC66]✓[/] {name}")
            else:
                lines.append(f"  [#8A8A8A]…[/] {name}")
        self.query_one("#docker-health", Static).update("\n".join(lines))

    def _all_healthy(self) -> None:
        self._log(
            f"\n[bold green]All services are healthy![/]\n"
            f"[bold]Dashboard:[/]     {self.state.dashboard_url}\n"
            f"[bold]Engine API:[/]    http://localhost:8000\n"
            f"[bold]OTel Collector:[/] http://localhost:4317 (gRPC) / :4318 (HTTP)"
        )
        self._enable_dashboard()

    def _enable_dashboard(self) -> None:
        self.query_one("#btn-dashboard", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-dashboard":
            import webbrowser
            webbrowser.open(self.state.dashboard_url)
        elif event.button.id == "btn-done":
            self.app.exit()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class TraceCtrlSetup(App):
    """TraceCtrl first-time setup TUI."""

    CSS = """
    Screen {
        background: #040404;
        color: #F5F5F5;
    }

    /* ---------- Welcome ---------- */
    #welcome-art {
        color: #FC0404;
        text-align: center;
    }

    /* ---------- Titles & subtitles ---------- */
    #reg-title, #config-title, #confirm-title, #launch-title,
    #framework-title, #ocpath-title, #ocaction-title, #scan-title,
    #strands-title, #project-title, #docker-title {
        color: #F5F5F5;
        text-style: bold;
    }
    #reg-subtitle, #framework-subtitle, #ocpath-subtitle,
    #ocaction-subtitle, #strands-subtitle, #strands-info,
    #project-preview, #scan-note {
        color: #8A8A8A;
        margin: 0 2 1 2;
    }
    #ocaction-path {
        color: #00CC66;
        margin: 0 2 0 2;
    }

    /* ---------- Env preview ---------- */
    #env-preview {
        color: #AAAAAA;
        margin: 1 2;
        padding: 1;
        border: solid #222222;
    }

    /* ---------- Inputs & selects ---------- */
    Input {
        margin: 0 2 1 2;
    }
    Label {
        margin: 1 2 0 2;
        color: #8A8A8A;
    }
    Select {
        margin: 0 2 1 2;
    }

    /* ---------- Buttons ---------- */
    Button {
        margin: 1 2;
    }
    #btn-start, #btn-review, #btn-launch, #btn-register,
    #btn-openclaw, #btn-strands, #btn-scan, #btn-explore,
    #btn-next, #btn-continue, #btn-dashboard {
        background: #FC0404;
    }
    #btn-skip, #btn-back, #btn-done {
        background: #2A2A2A;
        color: #8A8A8A;
    }
    #btn-fix {
        background: #FF6B35;
    }

    /* ---------- Framework buttons ---------- */
    #framework-buttons {
        height: auto;
        margin: 1 2;
    }
    #framework-buttons Button {
        width: 100%;
        height: 3;
        margin: 0 0 1 0;
    }

    /* ---------- Action buttons ---------- */
    #ocaction-buttons {
        height: auto;
        margin: 1 2;
    }
    #ocaction-buttons Button {
        width: 100%;
        height: 3;
        margin: 0 0 1 0;
    }

    /* ---------- Path validation ---------- */
    #ocpath-status {
        margin: 0 2;
        height: 1;
    }

    /* ---------- Scan screen ---------- */
    #scan-summary {
        margin: 0 2 1 2;
        text-style: bold;
    }
    #scan-loading {
        margin: 1 2;
        height: 3;
    }
    #scan-tabs {
        height: auto;
        margin: 0 2 1 2;
    }
    #scan-tabs Button {
        min-width: 14;
        margin: 0 1 0 0;
    }

    DataTable {
        margin: 0 2 1 2;
        height: 1fr;
        border: solid #222222;
    }
    DataTable > .datatable--header {
        background: #1A1A1A;
        color: #F5F5F5;
        text-style: bold;
    }
    DataTable > .datatable--cursor {
        background: #2A2A2A;
    }
    DataTable > .datatable--even-row {
        background: #0A0A0A;
    }

    #scan-fix-log {
        margin: 0 2 1 2;
        border: solid #222222;
        height: auto;
        max-height: 8;
    }
    #scan-actions {
        height: auto;
    }

    /* ---------- Docker screen ---------- */
    #docker-log {
        margin: 1 2;
        border: solid #222222;
        height: 1fr;
    }
    #docker-health {
        margin: 0 2 1 2;
    }

    /* ---------- Shared ---------- */
    RichLog {
        margin: 1 2;
        border: solid #222222;
        height: 1fr;
    }
    Horizontal {
        height: auto;
    }
    LoadingIndicator {
        color: #FC0404;
    }
    """

    BINDINGS = [Binding("q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.state = WizardState()
        self.push_screen(WelcomeScreen())


# Alias for CLI entry point / SDK shim compatibility
TraceCtrlApp = TraceCtrlSetup

if __name__ == "__main__":
    TraceCtrlSetup().run()
