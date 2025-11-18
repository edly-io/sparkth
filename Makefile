# Default: show help when just running `make`
.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@echo "Usage: make \033[36m<target>\033[0m\n"
	@echo "\033[1mTargets:\033[0m"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo

##@ Setup
uv: ## Install uv if missing
	@command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

dev: uv ## Install dev dependencies
	uv sync --all-extras --dev

lock: uv ## Update lockfile
	uv lock

install: uv ## Install exact versions from lockfile
	uv sync --frozen

##@ Development
test: ## Run tests
	uv run pytest

cov: ## Run tests with coverage
	uv run pytest --cov-report=term-missing

lint: ## Lint with ruff
	uv run ruff check

fix: ## Auto-fix + format with ruff
	uv run ruff check --fix
	uv run ruff format

##@ Build
build: ## Build package
	uv build
