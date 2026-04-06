"""TraceCtrl TUI — first-time setup wizard."""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

try:
    from textual.app import App, ComposeResult
    from textual.screen import Screen
    from textual.widgets import Button, Input, Label, Static, RichLog, Select
    from textual.containers import Horizontal, Vertical
    from textual.binding import Binding
except ImportError:
    print("Textual not installed. Run: pip install textual rich")
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTER_URL = os.environ.get("TRACECTRL_REGISTER_URL", "https://tracectrl.ai/api/register")
REGISTERED_FLAG = Path.home() / ".tracectrl_registered"


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
                self.app.push_screen(ConfigScreen())
            else:
                self.app.push_screen(RegistrationScreen())


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
            self.app.push_screen(ConfigScreen())
        elif event.button.id == "btn-register":
            self._submit_registration()

    def _submit_registration(self) -> None:
        email = self.query_one("#reg_email", Input).value.strip()
        user_type_sel = self.query_one("#reg_user_type", Select)
        role_sel = self.query_one("#reg_role", Select)
        org_size_sel = self.query_one("#reg_org_size", Select)

        user_type = str(user_type_sel.value) if user_type_sel.value != Select.BLANK else ""
        role = str(role_sel.value) if role_sel.value != Select.BLANK else ""
        org_size = str(org_size_sel.value) if org_size_sel.value != Select.BLANK else None

        if not email or "@" not in email:
            self.notify("Please enter a valid email address", severity="error")
            return

        if not user_type:
            self.notify("Please select a user type", severity="error")
            return

        if not role:
            self.notify("Please select your role", severity="error")
            return

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
        self.app.push_screen(ConfigScreen())


class ConfigScreen(Screen):
    """Screen 2: Configuration form."""

    def compose(self) -> ComposeResult:
        yield Static("\n  Configuration\n", id="config-title")
        yield Label("Service Name")
        yield Input(value="my-agent-service", id="service_name")
        yield Label("OTel Collector Endpoint")
        yield Input(value="http://localhost:4317", id="endpoint")
        yield Label("Pipeline Interval (seconds)")
        yield Input(value="60", id="interval")
        yield Static("")
        yield Button("Review →", id="btn-review", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-review":
            config = {
                "service_name": self.query_one("#service_name", Input).value,
                "endpoint": self.query_one("#endpoint", Input).value,
                "interval": self.query_one("#interval", Input).value,
            }
            self.app.push_screen(ConfirmScreen(config))


class ConfirmScreen(Screen):
    """Screen 3: Review .env before writing."""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        env_content = self._build_env()
        yield Static("\n  Review your .env\n", id="confirm-title")
        yield Static(env_content, id="env-preview")
        yield Static("")
        yield Horizontal(
            Button("← Back", id="btn-back"),
            Button("Write .env & Launch →", id="btn-launch", variant="primary"),
        )

    def _build_env(self) -> str:
        return (
            f"# Generated by TraceCtrl TUI\n"
            f"TRACECTRL_ENDPOINT={self.config['endpoint']}\n"
            f"TRACECTRL_SERVICE_NAME={self.config['service_name']}\n"
            f"TRACECTRL_FAIL_SILENTLY=true\n"
            f"\n"
            f"CLICKHOUSE_HOST=clickhouse\n"
            f"CLICKHOUSE_PORT=9000\n"
            f"CLICKHOUSE_DB=tracectrl\n"
            f"PIPELINE_INTERVAL_SECONDS={self.config['interval']}\n"
            f"\n"
            f"ENGINE_URL=http://tracectrl-engine:8000\n"
            f"VITE_ENGINE_URL=http://localhost:8000\n"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-launch":
            env_path = REPO_ROOT / ".env"
            env_path.write_text(self._build_env())
            self.app.push_screen(LaunchScreen())


class LaunchScreen(Screen):
    """Screen 4: Docker Compose launch with live output."""

    def compose(self) -> ComposeResult:
        yield Static("\n  Launching TraceCtrl...\n", id="launch-title")
        yield RichLog(id="launch-log", highlight=True, markup=True)
        yield Button("Done", id="btn-done", variant="primary")

    def on_mount(self) -> None:
        log = self.query_one("#launch-log", RichLog)
        log.write("[bold green]✓[/] .env written successfully")
        log.write(f"[bold]Working directory:[/] {REPO_ROOT}")
        log.write("[bold]Running:[/] docker compose up -d\n")

        try:
            result = subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    log.write(line)
            if result.stderr:
                for line in result.stderr.strip().split("\n"):
                    log.write(line)

            if result.returncode == 0:
                log.write("\n[bold green]✓ All services launched![/]")
                log.write("\n[bold]Dashboard:[/] http://localhost:3000")
                log.write("[bold]Engine API:[/] http://localhost:8000")
                log.write("[bold]OTel Collector:[/] http://localhost:4317 (gRPC) / :4318 (HTTP)")
            else:
                log.write(f"\n[bold red]✗ docker compose exited with code {result.returncode}[/]")
        except FileNotFoundError:
            log.write("[bold yellow]⚠ Docker not found. Install Docker and run 'docker compose up -d' manually.[/]")
        except subprocess.TimeoutExpired:
            log.write("[bold yellow]⚠ Timeout waiting for docker compose. Check manually.[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-done":
            self.app.exit()


class TraceCtrlSetup(App):
    """TraceCtrl first-time setup TUI."""

    CSS = """
    Screen {
        background: #040404;
        color: #F5F5F5;
    }
    #welcome-art {
        color: #FC0404;
        text-align: center;
    }
    #reg-title, #config-title, #confirm-title, #launch-title {
        color: #F5F5F5;
        text-style: bold;
    }
    #reg-subtitle {
        color: #8A8A8A;
        margin: 0 2 1 2;
    }
    #env-preview {
        color: #AAAAAA;
        margin: 1 2;
        padding: 1;
        border: solid #222222;
    }
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
    Button {
        margin: 1 2;
    }
    #btn-start, #btn-review, #btn-launch, #btn-register {
        background: #FC0404;
    }
    #btn-skip {
        background: #2A2A2A;
        color: #8A8A8A;
    }
    RichLog {
        margin: 1 2;
        border: solid #222222;
        height: 1fr;
    }
    Horizontal {
        height: auto;
    }
    """

    BINDINGS = [Binding("q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen(WelcomeScreen())


# Alias for CLI entry point
TraceCtrlApp = TraceCtrlSetup

if __name__ == "__main__":
    TraceCtrlSetup().run()
