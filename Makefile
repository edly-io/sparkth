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
.PHONY: help uv dev lock install test test.backend test.frontend test.help build mypy \
        up dev.up down clean restart logs shell db-shell migrations base \
        frontend frontend.build frontend.format.check \
        lint lint.fix lint.format lint.frontend lint.backend \
        lint.fix.frontend lint.fix.backend lint.format.frontend lint.format.backend lint.help \
        create-user reset-password \
        api mcp cli

# --------------------------------------------------
# HELP
# --------------------------------------------------
help: ## Show this help
	@echo "Usage: make \033[36m<target>\033[0m [options]\n"
	@echo "\033[1mDocker Targets:\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z._-]+:.*?## / {if ($$1 ~ /^(up|dev\.up|down|clean|restart|logs|shell|db-shell)/) printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo "\n\033[1mFrontend Targets:\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z._-]+:.*?## / {if ($$1 ~ /^(frontend|frontend\.build|frontend\.format\.check)$$/) printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo "\n\033[1mRun Services Locally:\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$1 ~ /^(api|mcp|cli)$$/) printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo "\n\033[1mLocal Dev Targets:\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$1 ~ /^(uv|dev|lock|install|build|mypy)$$/) printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo "\n\033[1mLinting Targets:\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z._-]+:.*?## / {if ($$1 ~ /^(lint|lint\.fix|lint\.format|lint\.frontend|lint\.backend|lint\.fix\.frontend|lint\.fix\.backend|lint\.format\.frontend|lint\.format\.backend|lint\.help)$$/) printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo "\n\033[1mTesting Targets:\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z._-]+:.*?## / {if ($$1 ~ /^(test|test\.backend|test\.frontend|test\.help)$$/) printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo "\n\033[1mUser Management (In Docker):\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {if ($$1 ~ /^(create-user|reset-password)/) printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo

# --------------------------------------------------
# Docker Operations
# --------------------------------------------------
base: ## Build pre-baked base image with heavy Python deps (run when uv.lock or pyproject.toml changes)
	docker build -f Dockerfile.base -t sparkth-base:local .

up: ## Build and start app (frontend + API + db)
	@docker image inspect sparkth-base:local > /dev/null 2>&1 || { echo "sparkth-base:local not found — building base image first (one-time, ~20 min)..."; $(MAKE) base; }
	docker compose build api
	docker compose up -d

dev.up: ## Build and start app in dev mode (hot reload)
	@docker image inspect sparkth-base:local > /dev/null 2>&1 || { echo "sparkth-base:local not found — building base image first (one-time, ~20 min)..."; $(MAKE) base; }
	docker compose build api
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

down: ## Stop and remove containers
	docker compose down

clean: ## Stop and wipe database volume (fresh start)
	docker compose down -v db

restart: ## Restart all containers
	docker compose restart

logs: ## Tail logs for all containers
	docker compose logs -f

shell: ## Open shell inside the API container
	docker compose exec api /bin/bash

db-shell: ## Open Postgres shell inside DB container
	docker compose exec db psql -U sparkth -d sparkth

migrations: ## Run Alembic migrations in Docker
	docker compose -f docker-compose.yml up migrations

rag-cleanup: ## Run RAG cleanup task in Docker
	docker compose -f docker-compose.yml run --rm rag-cleanup 2>&1 | tail -1

app-restart: ## Restart the API container for fast iteration
	docker compose down api
	docker compose up api -d

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
	cd frontend && bun install && bun run dev

frontend.build: ## Build frontend (static export to frontend/out)
	cd frontend && bun install --frozen-lockfile && bun run build

frontend.format.check: ## Check frontend formatting (oxfmt)
	cd frontend && bun run format:check

# --------------------------------------------------
# Local Development (using uv)
# --------------------------------------------------
uv: ## Install uv if missing
	@command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

dev: uv ## Install dev dependencies locally
	uv sync --all-extras --dev
	uv run lefthook install

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

mypy: ## Run mypy type checking
	uv run mypy --strict app/ tests/

build: ## Build Python package (sdist + wheel)
	uv build

# --------------------------------------------------
# Testing
# --------------------------------------------------
test: ## Run tests (with-coverage=1 to include coverage)
	$(MAKE) test.frontend $(if $(with-coverage),with-coverage=1)
	$(MAKE) test.backend $(if $(with-coverage),with-coverage=1)

test.backend: ## Run backend tests (make test.backend [path] [with-coverage=1])
	uv run pytest $(if $(ARGS),$(ARGS),tests/) $(if $(with-coverage),--cov-report=term-missing)

test.frontend: ## Run frontend tests (make test.frontend [path] [with-coverage=1])
	cd frontend && bun run vitest run $(if $(with-coverage),--coverage) $(ARGS)

test.help: ## Show usage for all test commands
	@echo "Usage: make \033[36m<test-target>\033[0m [path] [with-coverage=1]\n"
	@echo "\033[1mTargets:\033[0m"
	@echo "  \033[36mtest\033[0m              Run all tests (frontend + backend)"
	@echo "  \033[36mtest.backend\033[0m      Run backend tests"
	@echo "  \033[36mtest.frontend\033[0m     Run frontend tests"
	@echo "\n\033[1mOptions:\033[0m"
	@echo "  \033[33m[path]\033[0m            File or directory to test (default: all tests)"
	@echo "  \033[33mwith-coverage=1\033[0m   Enable coverage reporting"
	@echo "\n\033[1mExamples:\033[0m"
	@echo "  make test"
	@echo "  make test with-coverage=1"
	@echo "  make test.backend tests/rag/"
	@echo "  make test.backend tests/rag/test_store.py"
	@echo "  make test.backend tests/rag/ with-coverage=1"
	@echo "  make test.frontend"
	@echo "  make test.frontend components/Button.test.tsx"
	@echo "  make test.frontend with-coverage=1"
	@echo

# --------------------------------------------------
# Linting
# --------------------------------------------------
lint: ## Check lint errors (frontend + backend)
	$(MAKE) lint.frontend
	$(MAKE) lint.backend

lint.fix: ## Auto-fix lint errors (frontend + backend)
	$(MAKE) lint.fix.frontend
	$(MAKE) lint.fix.backend

lint.format: ## Format code (frontend + backend, check=1 to check only)
	$(MAKE) lint.format.frontend $(if $(check),check=1)
	$(MAKE) lint.format.backend $(if $(check),check=1)

lint.frontend: ## Check frontend lint errors (oxlint)
	cd frontend && bun run lint

lint.backend: ## Check backend lint errors (ruff)
	uv run ruff check --select I
	uv run ruff check

lint.fix.frontend: ## Auto-fix frontend lint errors (oxlint)
	cd frontend && bun run lint:fix

lint.fix.backend: ## Auto-fix backend lint errors (ruff)
	uv run ruff check --select I --fix
	uv run ruff check --fix
	uv run ruff format

lint.format.frontend: ## Format frontend code (oxfmt, check=1 to check only)
	cd frontend && bun run $(if $(check),format:check,format)

lint.format.backend: ## Format backend code (ruff, check=1 to check only)
	uv run ruff format $(if $(check),--check)

lint.help: ## Show usage for all lint commands
	@echo "Usage: make \033[36m<lint-target>\033[0m [check=1]\n"
	@echo "\033[1mAggregate Targets:\033[0m"
	@echo "  \033[36mlint\033[0m                  Check lint errors (frontend + backend)"
	@echo "  \033[36mlint.fix\033[0m              Auto-fix lint errors (frontend + backend)"
	@echo "  \033[36mlint.format\033[0m           Format code (frontend + backend)"
	@echo "\n\033[1mFrontend Targets:\033[0m"
	@echo "  \033[36mlint.frontend\033[0m         Check frontend lint errors (oxlint)"
	@echo "  \033[36mlint.fix.frontend\033[0m     Auto-fix frontend lint errors (oxlint)"
	@echo "  \033[36mlint.format.frontend\033[0m  Format frontend code (oxfmt)"
	@echo "\n\033[1mBackend Targets:\033[0m"
	@echo "  \033[36mlint.backend\033[0m          Check backend lint errors (ruff)"
	@echo "  \033[36mlint.fix.backend\033[0m      Auto-fix backend lint errors (ruff)"
	@echo "  \033[36mlint.format.backend\033[0m   Format backend code (ruff)"
	@echo "\n\033[1mOptions:\033[0m"
	@echo "  \033[33mcheck=1\033[0m               Dry-run for format targets (no rewrites)"
	@echo "\n\033[1mExamples:\033[0m"
	@echo "  make lint"
	@echo "  make lint.fix"
	@echo "  make lint.format"
	@echo "  make lint.format check=1"
	@echo "  make lint.frontend"
	@echo "  make lint.format.backend check=1"
	@echo

# --------------------------------------------------
# Catch-all for argument forwarding
# --------------------------------------------------
%:
	@:
