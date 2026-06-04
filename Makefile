# Default: show help when just running `make`
.DEFAULT_GOAL := help

# Extract arguments for the catch-all targets (create-user, etc.)
ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))

.PHONY: help
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
.PHONY: uv
uv: ## Install uv if missing
	@command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

##@ Backing Services (Docker)
# In development the backend and frontend run natively; Docker only provides the
# Postgres, Redis, and Mailpit services they connect to (see docker-compose.yml).
.PHONY: services
services: ## Start backing services (Postgres, Redis, Mailpit) in the background
	docker compose up -d

.PHONY: down
down: ## Stop and remove service containers
	docker compose down $(ARGS)

.PHONY: clean
clean: ## Stop services and wipe data volumes (fresh start)
	docker compose down -v

.PHONY: restart
restart: ## Restart backing services
	docker compose restart

.PHONY: logs
logs: ## Tail logs (make logs [service] — omit service to tail all)
	docker compose logs -f $(ARGS)

.PHONY: db-shell
db-shell: ## Open Postgres shell inside DB container
	docker compose exec db psql -U $${POSTGRES_USER:-sparkth} -d $${POSTGRES_DB:-sparkth}

.PHONY: migrations
migrations: ## Apply Alembic migrations (native)
	uv run alembic upgrade head

.PHONY: rag-cleanup
rag-cleanup: ## Run the RAG cleanup task (native)
	uv run python -m app.rag.cleanup

##@ User Management
.PHONY: create-user
create-user: ## Create user (make create-user -- --username john)
	uv run python -m app.cli.main users create-user $(ARGS)

.PHONY: reset-password
reset-password: ## Reset password (make reset-password -- username)
	uv run python -m app.cli.main users reset-password $(ARGS)

##@ Frontend
.PHONY: frontend.build
frontend.build: ## Build frontend (static export to frontend/out)
	cd frontend && bun run build

.PHONY: frontend.install
frontend.install: ## Install exact frontend dependencies from lockfile
	cd frontend && bun install --frozen-lockfile

.PHONY: frontend
frontend: ## Run frontend dev server (hot reload)
	cd frontend && bun install && bun run dev

##@ Backend
.PHONY: backend.build
backend.build: ## Build Python package (sdist + wheel)
	uv build

.PHONY: backend.install
backend.install: uv ## Install exact backend dependencies from lockfile
	uv sync --frozen

.PHONY: backend.install.dev
backend.install.dev: uv backend.install.dev.requirements backend.install.dev.githooks ## Install dev requirements and githooks

.PHONY: backend.install.dev.requirements
backend.install.dev.requirements: ## Install exact backend dev dependencies from lockfile
	uv sync --frozen --dev

.PHONY: backend.install.dev.githooks
backend.install.dev.githooks: ## Install git hooks
	uv run lefthook install

.PHONY: lock
lock: ## Update lockfile
	uv lock

.PHONY: api
api: ## Run FastAPI server locally
	uv run fastapi dev app/main.py --host 0.0.0.0 --port 7727

.PHONY: mcp
mcp: ## Run MCP server locally (HTTP mode)
	uv run python -m app.mcp.main --transport http

.PHONY: cli
cli: ## Run CLI tool (make cli -- users --help)
	uv run python -m app.cli.main $(ARGS)

.PHONY: mypy
mypy: ## Run mypy type checking
	uv run mypy --strict app/ tests/

##@ Testing
.PHONY: test
test: ## Run tests (with-coverage=1 to include coverage)
	$(MAKE) test.frontend $(if $(with-coverage),with-coverage=1)
	$(MAKE) test.backend $(if $(with-coverage),with-coverage=1)

.PHONY: test.backend
test.backend: lint.backend mypy test.backend.pytest test.backend.format ## Run backend tests

.PHONY: test.backend.pytest
test.backend.pytest: ## Run backend unit tests (make test.backend.pytest [path] [with-coverage=1])
	uv run pytest $(ARGS) $(if $(with-coverage),--cov-report=term-missing)

.PHONY: test.backend.format
test.backend.format: ## Run backend formatting tests
	$(MAKE) lint.format.backend check=1

.PHONY: test.frontend
test.frontend: lint.frontend lint.frontend.react-doctor test.frontend.vitest test.frontend.format ## Run frontend linting, react-doctor, unit and formatting tests

.PHONY: test.frontend.vitest
test.frontend.vitest: ## Run frontend unit tests (make test.frontend.vitest [path] [with-coverage=1])
	cd frontend && bun run vitest run $(if $(with-coverage),--coverage) $(ARGS)

.PHONY: test.frontend.format
test.frontend.format: ## Run frontend formatting tests
	$(MAKE) lint.format.frontend check=1

##@ Linting
.PHONY: lint
lint: ## Check lint errors (frontend + backend)
	$(MAKE) lint.frontend
	$(MAKE) lint.backend

.PHONY: lint.fix
lint.fix: ## Auto-fix lint errors (frontend + backend)
	$(MAKE) lint.fix.frontend
	$(MAKE) lint.fix.backend

.PHONY: lint.format
lint.format: ## Format code (frontend + backend, check=1 to check only)
	$(MAKE) lint.format.frontend $(if $(check),check=1)
	$(MAKE) lint.format.backend $(if $(check),check=1)

.PHONY: lint.frontend
lint.frontend: ## Check frontend lint errors (oxlint)
	cd frontend && bun run lint

.PHONY: lint.backend
lint.backend: ## Check backend lint errors (ruff)
	uv run ruff check

# Base branch react-doctor diffs against; override in CI (e.g. origin/main).
REACT_DOCTOR_BASE ?= main
.PHONY: lint.frontend.react-doctor
lint.frontend.react-doctor: ## Run react-doctor on files changed vs REACT_DOCTOR_BASE (default main)
	cd frontend && bunx react-doctor@0.2.16 . --diff $(REACT_DOCTOR_BASE) --annotations --yes

.PHONY: lint.fix.frontend
lint.fix.frontend: ## Auto-fix frontend lint errors (oxlint)
	cd frontend && bun run lint:fix

.PHONY: lint.fix.backend
lint.fix.backend: ## Auto-fix backend lint errors (ruff)
	uv run ruff check --fix

.PHONY: lint.format.frontend
lint.format.frontend: ## Format frontend code (oxfmt, check=1 to check only)
	cd frontend && bun run $(if $(check),format:check,format)

.PHONY: lint.format.backend
lint.format.backend: ## Format backend code (ruff, check=1 to check only)
	uv run ruff format $(if $(check),--check)

# Catch-all for argument forwarding
%:
	@:
