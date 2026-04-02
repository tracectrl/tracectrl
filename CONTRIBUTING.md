# Contributing to TraceCtrl

Thanks for your interest in contributing to TraceCtrl! This document covers the process for contributing to the project.

## Contributor License Agreement (CLA)

Before your first pull request can be merged, you must sign our [Contributor License Agreement](CLA.md). This is handled automatically — when you open a PR, the CLA Assistant bot will prompt you to sign by commenting on the PR. You only need to sign once.

**Why?** TraceCtrl uses a split licensing model (Apache-2.0 for the SDK, BUSL-1.1 for the platform). The CLA ensures Cloudsine Pte Ltd can include contributions under both license tracks while you retain ownership of your work. See [CLA.md](CLA.md) for the full explanation.

If you are contributing on behalf of your employer, please have an authorized representative contact info@tracectrl.ai to execute a Corporate CLA.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a branch from `main` for your changes
4. Make your changes
5. Run linting and tests before submitting:
   ```bash
   make lint
   make test
   ```
6. Open a pull request against `main`

## Development Setup

```bash
# Clone and set up
git clone https://github.com/<your-fork>/tracectrl.git
cd tracectrl

# Install SDK in editable mode
pip install -e ./sdk/tracectrl
pip install -r engine/requirements.txt

# Start the platform (requires Docker)
cp .env.example .env
docker compose up -d

# Run tests
make test

# Run linter
make lint
```

## Project Structure

| Directory | License | What it is |
|-----------|---------|------------|
| `sdk/` | Apache-2.0 | Python SDK and framework instrumentors |
| `engine/` | BUSL-1.1 | FastAPI intelligence engine |
| `ui/` | BUSL-1.1 | React dashboard |
| `config/` | BUSL-1.1 | OTel Collector and ClickHouse configuration |
| `setup/` | BUSL-1.1 | TUI setup wizard |

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Include a clear description of what changed and why
- Ensure `make lint` and `make test` pass
- Update documentation if your change affects user-facing behavior
- The CLA check must pass before merge

## Reporting Issues

Open an issue on GitHub with:
- A clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- TraceCtrl version and environment details

## Code of Conduct

Be respectful. We're building security tooling for the AI ecosystem — constructive collaboration makes the project better for everyone.

## Questions?

- Open a GitHub Discussion for general questions
- Email info@tracectrl.ai for licensing or CLA questions
