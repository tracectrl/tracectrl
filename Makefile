.PHONY: setup setup-dev dev pull test lint build clean tui scan demo

# ── Setup (uses published PyPI packages) ───────────────
setup:
	python3 -m pip install --upgrade pip
	pip install tracectrl tracectrl-scanner
	@echo "\n✓ Setup complete. Run 'make start' to launch the stack."

# ── Setup for contributors (editable installs) ─────────
setup-dev:
	python3 -m pip install --upgrade pip
	pip install -e ./scanner
	pip install -e ./sdk/tracectrl
	pip install -r engine/requirements.txt
	pip install pytest ruff
	@echo "\n✓ Dev setup complete. Run 'make dev' to start the stack."

# ── Start (pull latest images + run) ───────────────────
start: pull
	docker compose up -d
	@echo "\n✓ Stack running. Dashboard → http://localhost:3000"

# ── Pull latest GHCR images ────────────────────────────
pull:
	docker pull ghcr.io/tracectrl/tracectrl-engine:latest
	docker pull ghcr.io/tracectrl/tracectrl-ui:latest

# ── Dev (hot reload, local build) ──────────────────────
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# ── Test ───────────────────────────────────────────────
test:
	pytest tests/ -v

# ── Lint ───────────────────────────────────────────────
lint:
	ruff check sdk/ engine/ scanner/ tests/

# ── Build images locally ───────────────────────────────
build:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml build

# ── TUI Setup ─────────────────────────────────────────
tui:
	python3 setup/tui.py

# ── Scan ───────────────────────────────────────────────
scan:
	tracectrl scan ~/.openclaw/

# ── Demo ───────────────────────────────────────────────
demo:
	@echo "Running demo agent..."
	python3 examples/demo_agent.py
	@echo "\n✓ Check http://localhost:3000 to see traces"

# ── Clean ──────────────────────────────────────────────
clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
