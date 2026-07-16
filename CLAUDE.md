# Sparkth

AI-first, open-source learning platform by Edly. Provides a unified framework for course generation with integrated AI capabilities exposed via a Model Context Protocol (MCP) server.

Useful URLs:

- REST API: `/api/`
- MCP server: `/ai/mcp`
- Docs: `/docs`

## Tech Stack

**Backend:** Python 3.14, FastAPI, SQLModel (async), PostgreSQL, Redis, Alembic, FastMCP, LangChain (OpenAI/Anthropic/Google), pydantic-settings

**Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS 4, Radix UI, Bun

**Tooling:** uv (Python packages), Ruff (lint/format), mypy strict, pytest + pytest-asyncio, Docker Compose

## Key Directories

The package has three tiers: `core/` (shared internals plugins depend on), `lib/`
(the façade to core — the only surface plugins import from, stays outside `core/`),
and `plugins/` (the built-in plugins).

```
sparkth/
  core/          # Shared internals plugins depend on (reached only via sparkth/lib)
    config.py      # Settings; also encryption.py, security.py (JWT/OAuth), cache.py, db.py, email.py
    models/        # SQLModel DB models (base.py has TimestampedModel, SoftDeleteModel)
    plugins/       # Plugin framework: base.py (SparkthPlugin), loader.py, middleware.py, service.py (PluginService)
    permissions/   # Scoped-RBAC engine (roles, scopes, defaults)
    analytics/     # Analytics DB + emission gateway write path: engine/sessions, metadata registry, event schema hook (ANALYTICS_EVENTS), schemas (self-describing AnalyticsEventSchema base; plugins register via register_event_schema at import time), gateway (raw_events). Login emits user.logged_in.
    audit/         # Append-only audit trail: event classes, recorder, redaction, canonical bytes, request context
    routes/        # Plugin route-registration helpers
  lib/           # Curated public façade to core — the only surface plugins import from (see below)
  plugins/       # Built-in plugins: canvas/, openedx/, chat/, googledrive/, slack/ (each with tests/)
  api/v1/        # REST endpoints: auth, user, user-plugins, file-parser, events, permissions
  llm/           # LLM provider abstraction + config service (behind sparkth/lib/llm)
  mcp/           # FastMCP server, tool registration, prompts/
  services/      # Business logic layer (email verification, whitelist)
  rag/           # RAG pipeline: extraction, chunking, storage, agent-driven retrieval, cleanup
  cli/           # Typer CLI (user and role management)
  main.py        # FastAPI app assembly + lifespan
  migrations/
    app/         # Alembic versions for the main application DB
    analytics/   # Alembic versions for the separate analytics DB (TimescaleDB)

frontend/
  app/           # Next.js pages: login, register, dashboard/[pluginName]
  plugins/       # Plugin UI implementations (chat/, google-drive/)
  lib/plugins/   # Plugin system: types.ts, registry.ts, context.tsx
  components/    # Reusable UI components (settings/, ui/)

tests/           # Core / cross-cutting tests: api/, analytics/, core/, llm/, permissions/, rag/, services/
                 # Plugin tests are co-located (sparkth/plugins/<plugin>/tests/).
                 # Shared fixtures: sparkth/lib/testing.py. See "Test Layout".
.github/workflows/ # CI: lint → type-check → test on every PR
```

## Public Library (`sparkth/lib/`)

`sparkth/lib/` is the curated, stable API that application code **and plugins** import
from, instead of reaching into `sparkth.core.*` (or other internal packages) directly
— every internal symbol a plugin imports becomes an implicit public API and blocks
refactoring (see issue #379). When a core capability is needed beyond `sparkth/core`,
expose it through `sparkth/lib` and import it from there, never from `sparkth.core.*`,
`sparkth.llm.*`, or `sparkth.rag.*`.

The module-by-module reference is generated from the docstrings — build it with
`make docs` (see the [Python API reference](docs/reference/lib.md)). Do not maintain an
API listing here or in the README; keep the docstrings authoritative.

## Essential Commands

```bash
# Backing services (Docker): Postgres, Redis, Mailpit — the backend/frontend run natively
make services.up     # Start backing services in the background
make services.down   # Stop service containers
make services.clean  # Stop services + wipe data volumes

# Local backend (requires uv) — connects to the backing services above
make backend.install.dev    # Install dev dependencies
make backend.up.dev         # FastAPI on http://0.0.0.0:7727 (MCP server mounted at /ai/mcp; hot reload)
make test                   # Run all tests (frontend + backend)
make test.backend           # Run all backend tests
make test.backend.pytest    # Run unit tests with pytest
make test.backend.format    # Run backend formatting tests
make test.frontend          # Run all frontend tests
make test.frontend.vitest   # Run unit tests with vitest
make test.frontend.format   # Run frontend formatting tests
make test.e2e               # Run Playwright E2E tests against an ephemeral SQLite DB (see README.md)
make test.e2e.ui            # Run Playwright E2E tests in interactive UI mode
make test.e2e.install       # Install Playwright browsers (one-time)
make mypy                   # mypy --strict

# Linting
make lint                    # Check lint errors (frontend + backend)
make lint.fix                # Auto-fix lint errors (frontend + backend)
make lint.format             # Format code (frontend + backend)
make lint.format check=1     # Dry-run format check (no rewrites)
make lint.frontend           # Check frontend lint errors (oxlint)
make lint.backend            # Check backend lint errors (ruff)
make lint.fix.frontend       # Auto-fix frontend lint errors (oxlint)
make lint.fix.backend        # Auto-fix backend lint errors (ruff)
make lint.format.frontend    # Format frontend code (oxfmt)
make lint.format.backend     # Format backend code (ruff)
make lint.frontend.react-doctor  # React health check on files changed vs main (CI gate)

# Local frontend
make frontend.up.dev # Next.js dev server on :3000 (proxies /api to the backend; needs `make backend.up.dev` running)
make frontend.build  # Static export → frontend/out/ (served by the backend in production)
make frontend.build.api  # Regenerate frontend/lib/api/generated.ts from the backend OpenAPI schema (run after backend API changes; called automatically by make frontend.build)

# Database
make migrations         # Apply Alembic migrations for both app and analytics databases (native)
make analytics-backfill # Full-refresh TimescaleDB continuous aggregates (run once after an analytics migration adds one; no-op on SQLite). Pass -- --name <cagg> to target one
make services.logs      # Tail logs for the service containers (make services.logs [service])
make db-shell           # PostgreSQL shell
make db-shell-analytics  # PostgreSQL shell on the analytics database
make create-user        # Create user (pass args after --)

# Documentation (mkdocs + mkdocstrings; docs deps in the isolated `docs` group)
make docs               # Build the docs site (guides + generated Python API reference) to site/
make docs.serve         # Live-preview the docs site at http://127.0.0.1:8000
```

## Environment Setup

`.env` is committed with working dev defaults (localhost-first: it points at the backing services published by `docker-compose.yml`). For sensitive credentials (Google OAuth, Slack) and local overrides, create a `.env.local` file (git-ignored) — it takes precedence over `.env` and is read by both the native backend and `docker compose`. See the production checklist at the top of `.env` for values that must change before deploying.

**`.env` is the source of truth for the full, current list of variables and their dev
defaults** — it carries a comment on every variable, so read it there rather than
duplicating the list here.

CI uses `DATABASE_URL=sqlite+aiosqlite:///./test.db`. Tests always run against SQLite.

### Adding a new environment variable

**`.env` is always the source of truth.** It must have complete, up-to-date information about every variable the application needs.

- **Non-sensitive variable** — add it to `.env` with an appropriate dev default value.
- **Sensitive variable** (API keys, OAuth secrets, passwords) — add it to the user's `.env.local` (git-ignored), but add a reference to it in the `# !! MUST change in production !!` comment block at the top of `.env` so developers know it exists and where to set it.

Never add a variable only to `.env.local` without a corresponding reference in `.env`.

## Development Workflow: Test-Driven Development (TDD)

**Always follow TDD. Write tests before implementation — no exceptions.**

### The Mandatory TDD Cycle

For every new feature, endpoint, service method, utility, or plugin tool:

1. **Write the test first** — create or update the relevant test file, following the [Test Layout](#test-layout) rules below.
2. **Confirm the test fails** — the test must fail before any implementation exists (red phase)
3. **Write the minimum implementation** to make the test pass (green phase)
4. **Refactor** while keeping all tests green

> Never write implementation code before a corresponding failing test exists.

For bug fixes: write a test that reproduces the bug first, verify it fails, then fix.

## Documentation Hygiene

**Always update documentation alongside every code change — no exceptions.**

Documentation includes:

- **Docstrings** — module, class, and function docstrings must reflect current behaviour. If a function no longer does what its docstring says, update the docstring in the same commit.
- **Inline comments** — remove or update comments that describe logic that has changed. Never leave comments that contradict the code.
- **Markdown files** — `CLAUDE.md`, `README.md`, plugin guides, and any other `.md` files must be updated when commands, architecture, configuration, or behaviour they describe changes.

The rule applies to both new work and incidental changes. If you touch a file and notice a stale docstring or comment nearby, fix it in the same commit.

**Permission system → docs.** Whenever you change the permission system — declare or remove a permission or scope kind (via `Permission.create()` / `PermissionScope.create()`, which feed the `PERMISSIONS` / `PERMISSION_SCOPES` hooks), add or remove a role, or change how scopes, the lookup helpers, or assignments behave — update the permissions guide [`docs/guides/permissions.md`](docs/guides/permissions.md) in the same PR (the class/function detail comes from the docstrings, rendered by `make docs`). The shipped scopes/roles tables and the extension guide must stay accurate so the docs grow with the codebase and are reviewed alongside the change.

### Test Layout

Tests live next to the code they own, so each plugin stays a self-contained, portable unit (plugins are expected to move into their own repositories eventually). Place a new test by what it covers:

- **Plugin** → `sparkth/plugins/<plugin>/tests/test_*.py` (canvas, chat, googledrive, openedx, slack)
- **Core / cross-cutting** → `tests/<module>/test_*.py` mirroring `sparkth/<module>/` (api, core, llm, permissions, rag, services)

  RAG is core, so RAG tests live at `tests/rag/` (not co-located under `sparkth/rag/`); the
  RAG MCP tooling under `sparkth/rag/mcp/` is mirrored by `tests/rag/mcp/`.

How the suite is wired:

- Discovery is plain `pytest` recursion from the repo root — any new `…/tests/` directory is picked up automatically. **Do not add `testpaths` to `pyproject.toml`**: it risks silently dropping a test dir.
- Shared fixtures (`engine`, `session`, `client`, `setup_plugins_and_user`, …) and the generic test environment live in [`sparkth/lib/testing.py`](sparkth/lib/testing.py), registered globally as a pytest plugin by the root [`conftest.py`](conftest.py) (`pytest_plugins = ["sparkth.lib.testing"]`). No per-conftest fixture imports are needed — just use the fixtures by name.
- The three required-and-defaultless `Settings` fields (`DATABASE_URL`, `SECRET_KEY`, `LLM_ENCRYPTION_KEY`) are set by `sparkth/lib/testing.py`; tests must not redefine them. Plugin-specific test env (e.g. `SLACK_*`) belongs in that plugin's own conftest.
- A file named `tests.py` inside a package is **not** collected — pytest only collects `test_*.py`.

## Database Migrations

**Never edit an existing migration file. No exceptions.**

Any schema change — add column, drop column, rename, alter type, add index — requires a new Alembic migration file.

Editing an existing migration breaks environments that have already applied it, causing irreproducible state across dev, staging, and production.

To create a new migration, use:
```bash
alembic revision --autogenerate -m "describe your change"
```

**Never hand-craft migration filenames or revision IDs.** Always use `alembic revision --autogenerate` — it generates a valid random hex revision ID. Hand-crafted IDs risk tooling confusion and non-hex characters that break Alembic expectations.

To apply all pending migrations:
```bash
make migrations
```

The project has **two independent Alembic lineages**: the application database
(`alembic.ini` → `sparkth/migrations/app/`) and the analytics database
(`alembic_analytics.ini` → `sparkth/migrations/analytics/`). `make migrations` applies
both. Generate an analytics migration with
`alembic -c alembic_analytics.ini revision --autogenerate -m "..."`. The two
databases never share metadata: app models use `SQLModel.metadata`, analytics
tables use `sparkth.core.analytics.models.analytics_metadata`.

**Continuous aggregates need a one-off backfill after migrating.** A TimescaleDB
continuous aggregate is created `WITH NO DATA` (creating it with data would backfill
inside Alembic's transaction), and its refresh policy only covers a trailing window —
so once the first policy run advances the materialization watermark, buckets older than
that window vanish from the view and pre-migration history is lost. After applying an
analytics migration that adds a continuous aggregate, run `make analytics-backfill` once
on PostgreSQL to full-refresh it (`refresh_continuous_aggregate` over the whole range).
It is idempotent and a no-op on SQLite.

### Preventing Split Heads

Multiple Alembic heads occur when two branches each generate a migration from the same parent revision and merge independently. Before creating a new migration, always check for existing heads:

```bash
alembic heads
```

If there are already multiple heads, merge them first:
```bash
alembic merge heads -m "merge migration heads"
```

After merging a PR that adds a migration, any other in-flight branch that also adds a migration must rebase so its `down_revision` points to the new tip — otherwise merging it will create another split head.

## Exception Handling

**Never use bare `except Exception` blocks. Always catch specific exception types.**

This rule applies to all layers: API endpoints, services, plugins, MCP tools, and utilities.

### Rules

1. **Catch only what you expect.** Name the exact exception(s) a call can raise.
2. **Always log the exception** with enough context to diagnose the failure (module, operation, relevant IDs).
3. **Re-raise or not — developer's call.** If the caller can recover or needs to know, re-raise (the original or a domain-specific exception). If the error is fully handled at this level, swallowing is acceptable — but the log entry is still mandatory.
4. **Never silence exceptions silently.** A bare `except` or `except Exception` with no log is always wrong.

### Examples

```python
# ✅ Good — specific exception, logged, re-raise is a conscious choice
from sparkth.lib.log import get_logger

logger = get_logger(__name__)

# Re-raising (caller needs to know)
try:
    result = await canvas_client.get_course(course_id)
except HTTPStatusError as exc:
    # When you need the full traceback (not just the message):
    logger.exception("Canvas API error fetching course %s", course_id)
    # or equivalently:
    logger.error("Canvas API error fetching course %s: %s", course_id, exc, exc_info=True)
    raise

# Not re-raising (fully handled here)
try:
    await cache.set(key, value)
except RedisError as exc:
    logger.warning("Cache write failed for key %s: %s", key, exc)
    # continue without cache — non-fatal

# ✅ Good — multiple specific exceptions
try:
    data = json.loads(raw)
except (json.JSONDecodeError, UnicodeDecodeError) as exc:
    logger.error("Failed to parse response payload: %s", exc)
    raise ValueError("Invalid response format") from exc

# ❌ Bad — bare except, no log
try:
    result = await some_service.call()
except Exception:
    pass

# ❌ Bad — catches too broadly, replaces with a vague error
try:
    result = await some_service.call()
except Exception as exc:
    raise RuntimeError("something went wrong") from exc
```

### Choosing whether to re-raise

| Situation | Recommendation |
|---|---|
| Error is fatal to the current request/operation | Re-raise (original or domain exception) |
| Error is non-fatal and a fallback exists | Swallow — but log at `warning` or `error` level |
| Unsure | Re-raise — it's always safer to surface than to hide |

### Finding the right exceptions to catch

- Check the library's documentation or source for declared exceptions.
- For `httpx` use `httpx.HTTPStatusError`, `httpx.RequestError`.
- For SQLAlchemy/SQLModel use `sqlalchemy.exc.SQLAlchemyError` and its subclasses.
- For Redis use `redis.exceptions.RedisError` and its subclasses.
- For FastAPI/Starlette use `fastapi.HTTPException`, `starlette.exceptions.HTTPException`.
- For LangChain use `langchain_core.exceptions.LangChainException`, `OutputParserException`, and provider-specific errors.
- For standard I/O use `OSError`, `FileNotFoundError`, `PermissionError`, etc.
- For Pydantic use `pydantic.ValidationError`.

### Domain exceptions → HTTP responses (REST routes)

REST routes must not repeat `try/except → raise HTTPException(...)` for every domain error.
HTTP status decisions live in one API-layer mapping, not scattered through business-logic
routes.

1. **Raise HTTP-agnostic domain exceptions.** Services, engines, and plugins raise plain
   `Exception` subclasses (e.g. `RoleNotFound`); a domain exception never carries an HTTP
   status. HTTP is strictly an API-layer concern.

2. **Register the type → status mapping once**, with
   `register_exception_handler(ExcClass, status_code)` from
   [`sparkth.lib.exceptions.handlers`](sparkth/lib/exceptions/handlers.py) — core registers at
   import, a plugin from its `__init__`. `assemble_app` wires the registry onto the app at
   startup, and Starlette dispatches by walking the raised exception's `__mro__`, so a mapping
   on a base class also covers its subclasses. The route just raises the exception; the
   framework renders it as `{"detail": str(exc)}` with the mapped status.

3. **Design exceptions so the mapping is 1-to-1.** Each exception class must mean exactly one
   thing, so it maps unambiguously to a single status (`RoleNotFound` → 404,
   `RoleAlreadyExists` → 409, `RoleInUse` → 409). If one failure would need different statuses
   in different places, split it into distinct per-cause classes — do not overload one class.

4. **`try/except` in a route is the exception, not the rule.** Reach for it only when the
   status is genuinely context-dependent — the *same* domain exception must become a
   *different* HTTP status depending on the calling route. Then catch the specific type
   locally and translate to the appropriate `HTTPException` (catch-and-translate at the route
   boundary), still following the Rules above (log with context). A type that always maps to
   the same status must go through the registry, never an inline `try/except`.

5. **Let boundary validation reject malformed input.** Typed path/query params and request
   models turn bad input into a `422` before it reaches domain logic — do not hand-validate it
   in the route.

## Commit Messages

Every commit must follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/),
enforced by [`commitlint`](.github/workflows/commitlint.yml) on every PR.

```
<type>[(<scope>)]: <short description>

[optional body — explain WHY, not what]
```

**Types** (all conventional-commits types are accepted):

| Type | Use for |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or correcting tests |
| `docs` | Documentation only |
| `chore` | Maintenance tasks (dependency bumps, tooling config, …) |
| `build` | Changes to the build system or external dependencies |
| `ci` | Changes to CI configuration files and scripts |
| `perf` | Performance improvement |
| `revert` | Reverts a previous commit |
| `style` | Formatting changes that do not affect meaning |

**Scope** (optional, but recommended for clarity):
Common scopes: `api` | `frontend` | `plugins` | `rag` | `mcp` | `migrations` | `ci` | `core` — custom scopes are fine when none of these fit (e.g. `auth`, `docker`, `deps`).

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

docs: update environment variable reference table
```

## Pull Request Descriptions

Every PR must use the template in [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md). It auto-populates on GitHub.

**Rules:**
- Title: `<type>[(<scope>)]: short description` — max 70 chars, lowercase
- "What" must name the problem solved, not just the mechanism
- Every non-trivial code path needs a test step
- Flag breaking changes and migration requirements explicitly — never bury them

## Additional Documentation

| Topic | File |
|---|---|
| Architectural patterns & design decisions | [.claude/docs/architectural_patterns.md](.claude/docs/architectural_patterns.md) |
| Backend plugin development guide | [docs/guides/plugins.md](docs/guides/plugins.md) |
| Frontend plugin development guide | [docs/guides/frontend-plugins.md](docs/guides/frontend-plugins.md) |
| Permissions guide | [docs/guides/permissions.md](docs/guides/permissions.md) |
| Configuration guide (setup) | [docs/guides/configuration.md](docs/guides/configuration.md) |
| Configuration reference (variables) | [docs/reference/configuration.md](docs/reference/configuration.md) |
| User management guide | [docs/guides/user-management.md](docs/guides/user-management.md) |
| GitHub project management (issues, PRs, LLM notices) | [.claude/skills/sparkth-project-management/SKILL.md](.claude/skills/sparkth-project-management/SKILL.md) |

## GitHub Project Management

When creating or editing GitHub issues, posting proposed solutions, opening pull requests, or committing LLM-generated code, follow the conventions in the [`sparkth-project-management`](.claude/skills/sparkth-project-management/SKILL.md) skill.
