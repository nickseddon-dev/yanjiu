# Contributing to quant-os

## Overview

quant-os is a monorepo for a crypto social sentiment quantitative trading system.
It consists of research + execution on physically separated hosts, using NautilusTrader
for live execution and Qlib for research.

## Repository Structure

```
quant-os/
├── packages/       # Shared Python packages (schema, adapters, rules)
├── services/       # 10 microservice FastAPI apps
├── libs/           # Fork extensions (nautilus_ext, qlib_ext)
├── apps/           # End-user apps (ops_dashboard, analytics)
├── infra/          # Docker, compose, monitoring configs
├── tests/          # Integration tests
└── docs/           # Architecture docs, runbooks
```

## Development Setup

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Git

### Initial Setup

```bash
# Clone the repo
git clone git@github.com:nickseddon-dev/yanjiu.git quant-os
cd quant-os

# Install Python dependencies
pip install -e packages/common_schema \
               -e packages/event_schema \
               -e packages/feature_registry \
               -e packages/model_registry \
               -e packages/risk_rules \
               -e packages/cost_models \
               -e packages/adapters

# Copy and configure environment
cp infra/compose/.env.example .env
# Edit .env with your values

# Start infrastructure
docker compose -f infra/compose/docker-compose.yml up -d

# Verify services
curl http://localhost:8090/health   # signal_bridge
curl http://localhost:8091/health   # data_gateway
```

## Running Tests

```bash
# Unit tests (packages + libs)
pytest packages/ libs/

# Integration tests (requires docker compose up)
pytest tests/integration/ -v

# Full test suite
pytest --ignore=tests/integration/
```

## Running Services Locally

Each service can be run directly with Python:

```bash
# Terminal 1: data_gateway
python -m data_gateway.main

# Terminal 2: signal_bridge
python -m signal_bridge.main

# etc.
```

Or via docker compose (all services):

```bash
docker compose -f infra/compose/docker-compose.yml up --build
```

## Adding a New Service

1. Create `services/<my_service>/__init__.py`
2. Create `services/<my_service>/main.py` (FastAPI app with `/health`)
3. Create `services/<my_service>/Dockerfile`
4. Create `services/<my_service>/pyproject.toml`
5. Add to `infra/compose/docker-compose.yml`
6. Add to `.github/workflows/ci.yml` and `.github/workflows/docker.yml`
7. Add integration tests in `tests/integration/`
8. Add health check fixture in `tests/conftest.py`

## Code Style

- Line length: 100 chars (ruff)
- Type hints: strict mypy
- Docstrings: Google style for public classes/methods
- No hardcoded secrets — use environment variables

## Commit Messages

Follow Conventional Commits:
- `feat: add new service`
- `fix: resolve signal TTL bug`
- `docs: update architecture diagram`
- `test: add signal flow integration tests`

## Pull Requests

1. Fork and create a feature branch: `feature/my-feature`
2. Run `ruff check . && ruff format . && mypy packages/ libs/`
3. Ensure tests pass: `pytest`
4. Open PR targeting `main` or `master`