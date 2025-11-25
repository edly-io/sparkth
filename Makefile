# Default: show help when just running `make`
.DEFAULT_GOAL := help

# --------------------------------------------------
# PHONY TARGETS
# --------------------------------------------------
.PHONY: help uv dev lock install test cov start lint fix build create-user reset-password

# --------------------------------------------------
# HELP
# --------------------------------------------------
help: ## Show this help
	@echo "Usage: make \033[36m<target>\033[0m [options]\n"
	@echo "\033[1mTargets:\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo

# --------------------------------------------------
# Setup
# --------------------------------------------------
uv: ## Install uv if missing
	@command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

dev: uv ## Install dev dependencies
	uv sync --all-extras --dev

lock: uv ## Update lockfile
	uv lock

install: uv ## Install exact versions from lockfile
	uv sync --frozen

# --------------------------------------------------
# Development
# --------------------------------------------------
test: ## Run tests
	uv run pytest tests/

cov: ## Run tests with coverage
	uv run pytest tests/ --cov-report=term-missing

start: ## Start the API server
	uv run uvicorn app.main:app --reload

lint: ## Lint with ruff
	uv run ruff check

fix: ## Auto-fix + format with ruff
	uv run ruff check --fix
	uv run ruff format

# --------------------------------------------------
# Build
# --------------------------------------------------
build: ## Build package
	uv build

# --------------------------------------------------
# User Management
# --------------------------------------------------
# Use -- to separate make options from command arguments

ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))

create-user: ## Create a user (usage: make create-user -- --username john)
	uv run python -m app.cli.main users create-user $(ARGS)

reset-password: ## Reset password (usage: make reset-password -- username)
	uv run python -m app.cli.main users reset-password $(ARGS)

# --------------------------------------------------
# Catch-all target for forwarding --flags to commands
# --------------------------------------------------
%:
	@:
