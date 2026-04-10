# Sparkth

AI-first, open-source learning platform by Edly. Provides a unified framework for course generation with integrated AI capabilities exposed via a Model Context Protocol (MCP) server.

- REST API: `/api/` | MCP server: `/ai/mcp` | Docs: `/docs`
- Current version: `0.1.5`

## Tech Stack

**Backend:** Python 3.14, FastAPI, SQLModel (async), PostgreSQL, Redis, Alembic, FastMCP, LangChain (OpenAI/Anthropic/Google), pydantic-settings

**Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS 4, Radix UI, Bun

**Tooling:** uv (Python packages), Ruff (lint/format), mypy strict, pytest + pytest-asyncio, Docker Compose

## Key Directories

```
app/
  core/          # Settings, DB engines, security (JWT/OAuth), logger
  models/        # SQLModel DB models (base.py has TimestampedModel, SoftDeleteModel)
  api/v1/        # REST endpoints: auth, user, user-plugins, file-parser
  plugins/       # Plugin framework: base.py (SparkthPlugin, @tool), manager.py
  core_plugins/  # Built-in plugins: canvas/, openedx/, chat/, googledrive/
  mcp/           # FastMCP server, tool registration, prompts/
  services/      # Business logic layer, plugin adapters
  rag/           # Retrieval-augmented generation (loader, vectorstore, retriever)
  cli/           # Typer CLI (user management)
  migrations/    # Alembic versions

frontend/
  app/           # Next.js pages: login, register, dashboard/[pluginName]
  plugins/       # Plugin UI implementations (chat/, google-drive/)
  lib/plugins/   # Plugin system: types.ts, registry.ts, context.tsx
  components/    # Reusable UI components (settings/, ui/)

tests/           # pytest suite mirroring app structure (api/, chat/, mcp/, rag/)
.github/workflows/ # CI: lint → type-check → test on every PR
```

## Essential Commands

```bash
# Docker (recommended for full stack)
make up              # Build + start (PostgreSQL + Redis + API + frontend)
make dev.up          # Dev mode with hot reload
make down            # Stop containers
make clean           # Stop + wipe database volume

# Local backend (requires uv)
make dev             # Install dev dependencies
make api             # FastAPI on http://0.0.0.0:7727
make mcp             # MCP server (HTTP mode)
make test            # Run pytest
make cov             # Tests with coverage
make lint            # Ruff lint
make fix             # Ruff autofix + format
make mypy            # mypy --strict

# Local frontend
make frontend        # Next.js dev server on :3000
make frontend.build  # Static export → frontend/out/
make frontend.lint   # ESLint

# Database
make migrations      # Run pending Alembic migrations
make shell           # Shell inside API container
make db-shell        # PostgreSQL shell
make create-user     # Create user (pass args after --)
```

## Environment Setup

Copy `.env.example` → `.env`. Required variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key |
| `CHAT_ENCRYPTION_KEY` | Fernet key for conversation encryption |
| `CHAT_REDIS_URL` | Redis for chat session caching |
| `GOOGLE_CLIENT_ID/SECRET` | Google OAuth |

CI uses `DATABASE_URL=sqlite+aiosqlite:///./test.db`. Tests always run against SQLite.

## Development Workflow: Test-Driven Development (TDD)

**Always follow TDD. Write tests before implementation — no exceptions.**

### The Mandatory TDD Cycle

For every new feature, endpoint, service method, utility, or plugin tool:

1. **Write the test first** — create or update the relevant file under `tests/` mirroring the module path (e.g. `app/services/foo.py` → `tests/services/test_foo.py`)
2. **Confirm the test fails** — the test must fail before any implementation exists (red phase)
3. **Write the minimum implementation** to make the test pass (green phase)
4. **Refactor** while keeping all tests green

> Never write implementation code before a corresponding failing test exists.

For bug fixes: write a test that reproduces the bug first, verify it fails, then fix.

## Database Migrations

**Never edit an existing migration file. No exceptions.**

Any schema change — add column, drop column, rename, alter type, add index — requires a new Alembic migration file.

Editing an existing migration breaks environments that have already applied it, causing irreproducible state across dev, staging, and production.

To create a new migration, use:
```bash
alembic revision --autogenerate -m "describe your change"
```

To apply all pending migrations:
```bash
make migrations
```

## Commit Messages

Every commit must follow Conventional Commits. No exceptions.

```
<type>(<scope>): <short description>

[optional body — explain WHY, not what]
```

**Types:** `feat` | `fix` | `refactor` | `test` | `docs` | `chore`

**Scopes:** `api` | `frontend` | `plugins` | `rag` | `mcp` | `migrations` | `ci` | `core` — custom scopes are acceptable when none of these fit (e.g. `auth`, `docker`, `deps`)

**Rules:**
- Subject line: max 72 chars, lowercase, no trailing period
- Use imperative mood — "add auth" not "added auth"
- Body required when change needs context — why was this needed?
- One logical change per commit — do not bundle unrelated changes
- Never commit directly to `main`

**Examples:**
```
feat(api): add JWT refresh token endpoint

fix(migrations): handle missing plugins table on startup

refactor(rag): extract vectorstore into separate service

test(mcp): add integration tests for tool registration

chore(ci): pin uv version in GitHub Actions
```

## Pull Request Descriptions

Every PR must use the template in [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md). It auto-populates on GitHub.

**Rules:**
- Title: `<type>(<scope>): short description` — max 70 chars, lowercase
- "What" must name the problem solved, not just the mechanism
- Every non-trivial code path needs a test step
- Flag breaking changes and migration requirements explicitly — never bury them

## Additional Documentation

| Topic | File |
|---|---|
| Architectural patterns & design decisions | [.claude/docs/architectural_patterns.md](.claude/docs/architectural_patterns.md) |
| Plugin development guide | [app/plugins/PLUGIN_GUIDE.md](app/plugins/PLUGIN_GUIDE.md) |
| Frontend plugin development | [frontend/README.md](frontend/README.md) |
