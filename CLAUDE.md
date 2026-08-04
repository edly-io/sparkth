# Sparkth

AI-first, open-source learning platform by Edly. Provides a unified framework for course generation with integrated AI capabilities exposed via a Model Context Protocol (MCP) server.

Useful URLs:

- REST API: `/api/`
- MCP server: `/ai/mcp`
- Docs: `/docs`

## Key Directories

The package has three tiers: `core/` (shared internals plugins depend on), `lib/`
(the façade to core — the only surface plugins import from, stays outside `core/`),
and `plugins/` (the built-in plugins).

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

Run `make help` for the full, self-documenting target list.

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

Applies to every new feature, endpoint, service method, utility, and plugin tool. Place each new
test by the [Test Layout](#test-layout) rules below.

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

**TimescaleDB test lane.** The suite runs on in-memory SQLite by default. Tests that need a
real PostgreSQL/TimescaleDB — those exercising continuous aggregates, whose SQL (`_PG_SQL`)
and DDL (the analytics migrations) SQLite cannot represent — carry the `pg` marker (applied
module-wide via `pytestmark = pytest.mark.pg`) and live under
[`tests/analytics/pg/`](tests/analytics/pg/). They **skip** unless
`ANALYTICS_TEST_PG_URL` points at a real instance, so a plain `pytest` and the default CI job
stay green with no extra infrastructure. Run them with `make test.backend.analytics` (it starts the backing
services, which provide the Postgres/Timescale instance) or in the `analytics-timescale`
CI job (runs on every non-draft PR). The pg fixtures apply the analytics migrations to
the target DB (so the aggregate exists and the migration DDL is exercised) and reset state via
truncate + full refresh between tests — continuous aggregates can't use transaction-rollback
isolation because `refresh_continuous_aggregate` cannot run inside a transaction.

## Database Migrations

**Never edit an existing migration file. No exceptions.**

Any schema change — add column, drop column, rename, alter type, add index — requires a new Alembic migration file.

Editing an existing migration breaks environments that have already applied it, causing irreproducible state across dev, staging, and production.

Apply all pending migrations (both lineages) with:
```bash
make migrations
```

For everything else — generating a migration, the two independent app/analytics lineages, the
continuous-aggregate backfill step, and resolving split heads — use the
[`database-migrations`](.claude/skills/database-migrations/SKILL.md) skill.

## Exception Handling

**Never use bare `except Exception` blocks. Always catch specific exception types.**

This rule applies to all layers: API endpoints, services, plugins, MCP tools, and utilities.

### Rules

1. **Catch only what you expect.** Name the exact exception(s) a call can raise.
2. **Always log the exception** with enough context to diagnose the failure (module, operation, relevant IDs).
3. **Re-raise or not — developer's call.** If the caller can recover or needs to know, re-raise (the original or a domain-specific exception). If the error is fully handled at this level, swallowing is acceptable — but the log entry is still mandatory.
4. **Never silence exceptions silently.** A bare `except` or `except Exception` with no log is always wrong.

### Choosing whether to re-raise

| Situation | Recommendation |
|---|---|
| Error is fatal to the current request/operation | Re-raise (original or domain exception) |
| Error is non-fatal and a fallback exists | Swallow — but log at `warning` or `error` level |
| Unsure | Re-raise — it's always safer to surface than to hide |

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

## Commit Messages and Pull Requests

Commit message and PR-description conventions live in the
[`sparkth-project-management`](.claude/skills/sparkth-project-management/SKILL.md)
skill — follow it whenever creating or editing a GitHub issue, posting a proposed solution,
opening a pull request, or committing LLM-generated code. Conventional Commits are enforced by
[`commitlint`](.github/workflows/commitlint.yml) on every PR. Never commit directly to `main`.

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
| Database migrations (Alembic, split heads, backfill) | [.claude/skills/database-migrations/SKILL.md](.claude/skills/database-migrations/SKILL.md) |
