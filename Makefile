.PHONY: setup dev test lint build clean tui scan

# ── Setup ──────────────────────────────────────────────
setup:
	python3 -m pip install --upgrade pip
	pip install -e ./sdk/tracectrl
	pip install -e ./scanner
	pip install -r engine/requirements.txt
	pip install pytest ruff
	@echo "\n✓ Setup complete. Run 'make dev' to start the stack."

# ── Dev ────────────────────────────────────────────────
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# ── Test ───────────────────────────────────────────────
test:
	pytest tests/ -v

# ── Lint ───────────────────────────────────────────────
lint:
	ruff check sdk/ engine/ scanner/ tests/

# ── Build ──────────────────────────────────────────────
build:
	docker compose build

# ── TUI Setup ─────────────────────────────────────────
tui:
	python3 setup/tui.py

# ── Scan ───────────────────────────────────────────────
scan:
	tracectrl scan ~/.openclaw/

# ── Clean ──────────────────────────────────────────────
clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
