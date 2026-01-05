# Default: show help when just running `make`
.DEFAULT_GOAL := help

# --------------------------------------------------
# VARIABLES
# --------------------------------------------------
# Extract arguments for the catch-all targets (create-user, etc.)
ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))

# --------------------------------------------------
# PHONY TARGETS
# --------------------------------------------------
.PHONY: help uv dev lock install test cov lint fix build mypy \
        up dev.up down clean restart logs shell db-shell \
        api.up api.dev.up frontend frontend.build \
        create-user reset-password \
        api mcp cli

# --------------------------------------------------
# HELP
# --------------------------------------------------
help: ## Show this help
	@echo "Usage: make \033[36m<target>\033[0m [options]\n"
	@echo "\033[1mDocker Targets:\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z._-]+:.*?## / {if ($$1 ~ /^(up|dev\.up|api\.up|api\.dev\.up|down|clean|restart|logs|shell|db-shell)/) printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo "\n\033[1mFrontend Targets:\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z._-]+:.*?## / {if ($$1 ~ /^(frontend|frontend\.build)$$/) printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo "\n\033[1mRun Services Locally:\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$1 ~ /^(api|mcp|cli)$$/) printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo "\n\033[1mLocal Dev Targets:\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$1 ~ /^(uv|dev|lock|install|test|cov|lint|fix|build|mypy)/) printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo "\n\033[1mUser Management (In Docker):\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$1 ~ /^(create-user|reset-password)/) printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo

# --------------------------------------------------
# Docker Operations
# --------------------------------------------------
api.up: ## Start API and db only (background)
	docker compose up -d --build

api.dev.up: ## Start API in dev mode only (hot reload)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

up: frontend.build api.up ## Build frontend + start API (production)

dev.up: frontend.build api.dev.up ## Build frontend + start API in dev mode

down: ## Stop and remove containers
	docker compose down

clean: ## Stop and wipe database volume (fresh start)
	docker compose down -v

restart: ## Restart all containers
	docker compose restart

logs: ## Tail logs for all containers
	docker compose logs -f

shell: ## Open shell inside the API container
	docker compose exec api /bin/bash

db-shell: ## Open Postgres shell inside DB container
	docker compose exec db psql -U sparkth -d sparkth

# --------------------------------------------------
# User Management (Runs inside Docker)
# --------------------------------------------------
# These run inside the container so they can access the DB network
create-user: ## Create user (make create-user -- --username john)
	docker compose exec api python -m app.cli.main users create-user $(ARGS)

reset-password: ## Reset password (make reset-password -- username)
	docker compose exec api python -m app.cli.main users reset-password $(ARGS)

# --------------------------------------------------
# Frontend
# --------------------------------------------------
frontend: ## Run frontend dev server (hot reload)
	cd frontend && npm run dev

frontend.build: ## Build frontend (static export to frontend/out)
	cd frontend && npm run build

# --------------------------------------------------
# Local Development (using uv)
# --------------------------------------------------
uv: ## Install uv if missing
	@command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

dev: uv ## Install dev dependencies locally
	uv sync --all-extras --dev

lock: uv ## Update lockfile
	uv lock

install: uv ## Install exact versions from lockfile
	uv sync --frozen

api: ## Run FastAPI server locally
	uv run fastapi dev app/main.py --host 0.0.0.0 --port 7727

mcp: ## Run MCP server locally (HTTP mode)
	uv run python -m app.mcp.main --transport http

cli: ## Run CLI tool (make cli -- users --help)
	uv run python -m app.cli.main $(ARGS)

test: ## Run tests
	uv run pytest tests/

cov: ## Run tests with coverage
	uv run pytest tests/ --cov-report=term-missing

lint: ## Lint with ruff locally
	uv run ruff check --select I
	uv run ruff check

fix: ## Auto-fix + format locally
	uv run ruff check --select I --fix
	uv run ruff check --fix
	uv run ruff format

mypy: ## Run mypy type checking
	uv run mypy --strict app/ tests/

build: ## Build Python package (sdist + wheel)
	uv build

# --------------------------------------------------
# Catch-all for argument forwarding
# --------------------------------------------------
%:
	@:
