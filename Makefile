# BeliefOS developer task runner
# Usage: make <target>

PYTHON ?= python
PIP    ?= pip
DOCKER_COMPOSE ?= docker compose

.PHONY: help install install-dev test test-cov lint format clean run up down logs migrate docker-build dashboard

help:
	@echo "BeliefOS targets:"
	@echo "  install      Install package (editable)"
	@echo "  install-dev  Install with dev/test deps"
	@echo "  test         Run pytest"
	@echo "  test-cov     Run pytest with coverage"
	@echo "  lint         Run ruff (if installed)"
	@echo "  format       Run black (if installed)"
	@echo "  run          Run the FastAPI server locally"
	@echo "  dashboard    Open the HTML dashboard"
	@echo "  up           docker compose up -d"
	@echo "  down         docker compose down"
	@echo "  logs         docker compose logs -f"
	@echo "  migrate      Run database migrations"
	@echo "  docker-build Build the production image"
	@echo "  clean        Remove caches and build artifacts"

install:
	$(PIP) install -e .

install-dev:
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/

test-cov:
	$(PYTHON) -m coverage run --source=beliefos -m pytest tests/ -q
	$(PYTHON) -m coverage report --skip-covered

lint:
	$(PYTHON) -m ruff check beliefos tests

format:
	$(PYTHON) -m black beliefos tests

run:
	$(PYTHON) -m uvicorn beliefos.api.app:create_app --factory --reload --port 8000

dashboard:
	@echo "Open dashboard/index.html in a browser, or visit http://localhost:8000/dashboard when the API is running."

up:
	$(DOCKER_COMPOSE) up -d

down:
	$(DOCKER_COMPOSE) down

logs:
	$(DOCKER_COMPOSE) logs -f

migrate:
	$(PYTHON) -m beliefos.storage.migrate

docker-build:
	$(DOCKER_COMPOSE) build

clean:
	rm -rf .pytest_cache .coverage build dist *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
