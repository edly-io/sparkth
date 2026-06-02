# Default: show help when just running `make`
.DEFAULT_GOAL := help

# Extract arguments for the catch-all targets (create-user, etc.)
ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))

.PHONY: help uv lock test test.backend test.frontend mypy \
        up up.dev down clean restart logs shell db-shell migrations base \
        frontend frontend.build frontend.install \
        backend.build backend.install \
        lint lint.fix lint.format lint.frontend lint.backend \
        lint.fix.frontend lint.fix.backend lint.format.frontend lint.format.backend \
        create-user reset-password \
        api mcp cli

help: ## Show this help
	@echo "Usage: make \033[36m<target>\033[0m [options]"
	@awk ' \
		/^##@ / { printf "\n\033[1m%s:\033[0m\n", substr($$0, 5) } \
		/^[a-zA-Z._-]+:.*## / { \
			target = $$0; sub(/:.*/, "", target); \
			desc = substr($$0, index($$0, "## ") + 3); \
			printf "  \033[36m%-25s\033[0m %s\n", target, desc \
		} \
	' $(MAKEFILE_LIST)
	@echo

##@ Project Setup
uv: ## Install uv if missing
	@command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

##@ Docker Setup/Operations
base: ## Build pre-baked base image with heavy Python deps (run when uv.lock or pyproject.toml changes)
	docker build -f Dockerfile.base -t sparkth-base:local .

up: ## Build and start app (frontend + API + db)
	@docker image inspect sparkth-base:local > /dev/null 2>&1 || { echo "sparkth-base:local not found — building base image first (one-time, ~20 min)..."; $(MAKE) base; }
	docker compose build api
	docker compose up -d

up.dev: ## Build and start app in dev mode (hot reload)
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
	docker compose up migrations

rag-cleanup: ## Run RAG cleanup task in Docker
	docker compose run --rm rag-cleanup 2>&1 | tail -1

app-restart: ## Restart the API container for fast iteration
	docker compose down api
	docker compose up api -d

##@ User Management (Runs inside Docker)
# These run inside the container so they can access the DB network
create-user: ## Create user (make create-user -- --username john)
	docker compose exec api python -m app.cli.main users create-user $(ARGS)

reset-password: ## Reset password (make reset-password -- username)
	docker compose exec api python -m app.cli.main users reset-password $(ARGS)

##@ Frontend
frontend.build: ## Build frontend (static export to frontend/out)
	cd frontend && bun run build

frontend.install: ## Install exact frontend dependencies from lockfile
	cd frontend && bun install --frozen-lockfile

frontend: ## Run frontend dev server (hot reload)
	cd frontend && bun install && bun run dev

##@ Backend
backend.build: ## Build Python package (sdist + wheel)
	uv build

backend.install: uv ## Install exact backend dependencies from lockfile
	uv sync --frozen

backend.install.dev: uv ## Install exact backend dev dependencies from lockfile
	uv sync --frozen --all-extras --dev
	$(MAKE) backend.install.githooks

backend.install.githooks: ## Install git hooks
	uv run lefthook install

lock: ## Update lockfile
	uv lock

api: ## Run FastAPI server locally
	uv run fastapi dev app/main.py --host 0.0.0.0 --port 7727

mcp: ## Run MCP server locally (HTTP mode)
	uv run python -m app.mcp.main --transport http

cli: ## Run CLI tool (make cli -- users --help)
	uv run python -m app.cli.main $(ARGS)

mypy: ## Run mypy type checking
	uv run mypy --strict app/ tests/

##@ Testing
test: ## Run tests (with-coverage=1 to include coverage)
	$(MAKE) test.frontend $(if $(with-coverage),with-coverage=1)
	$(MAKE) test.backend $(if $(with-coverage),with-coverage=1)

test.backend: ## Run backend tests (make test.backend [path] [with-coverage=1])
	uv run pytest $(ARGS) $(if $(with-coverage),--cov-report=term-missing)

test.frontend: ## Run frontend tests (make test.frontend [path] [with-coverage=1])
	cd frontend && bun run vitest run $(if $(with-coverage),--coverage) $(ARGS)

##@ Linting
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
	uv run ruff check

lint.fix.frontend: ## Auto-fix frontend lint errors (oxlint)
	cd frontend && bun run lint:fix

lint.fix.backend: ## Auto-fix backend lint errors (ruff)
	uv run ruff check --fix

lint.format.frontend: ## Format frontend code (oxfmt, check=1 to check only)
	cd frontend && bun run $(if $(check),format:check,format)

lint.format.backend: ## Format backend code (ruff, check=1 to check only)
	uv run ruff format $(if $(check),--check)

# Catch-all for argument forwarding
%:
	@:
