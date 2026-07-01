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
    analytics/     # Analytics DB + emission gateway write path: engine/sessions, registries, schemas, gateway
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
expose it through `sparkth/lib` and import it from there.

Current modules (see the source for the full API — do not duplicate it here):

- [`sparkth/lib/log.py`](sparkth/lib/log.py) — logging. Obtain loggers via `get_logger`
  (never `logging.getLogger`); `configure_logging` is the single logging setup,
  called once per process entrypoint.
- [`sparkth/lib/db.py`](sparkth/lib/db.py) — database sessions. Use `session_scope` /
  `get_async_session` for the main DB; `analytics_session_scope` /
  `get_analytics_session` for the analytics DB. Implementation lives in
  `sparkth/core/db.py` (main) and `sparkth/core/analytics/db.py` (analytics).
- [`sparkth/lib/auth.py`](sparkth/lib/auth.py) — authentication dependency. Import
  `get_current_user` from here (the FastAPI dependency that resolves the authenticated
  `User` from the bearer token) — its single canonical home; every caller (routes, the
  permission gate) imports it from there. Implementation lives in `sparkth/lib/auth.py`.
- [`sparkth/lib/settings.py`](sparkth/lib/settings.py) — application settings. Read settings
  via `get_settings` (e.g. `get_settings().SECRET_KEY`); never import from
  `sparkth.core.config` directly. Implementation lives in `sparkth/core/config.py`.
- [`sparkth/lib/encryption.py`](sparkth/lib/encryption.py) — symmetric encryption. Import
  `get_encryption_service` / `EncryptionService` from here (Fernet encryption of secrets at
  rest, e.g. stored LLM API keys); never import from `sparkth.core.encryption` directly.
  Implementation lives in `sparkth/core/encryption.py`.
- [`sparkth/lib/models.py`](sparkth/lib/models.py) — data-model public API. Import the models
  plugins consume from here (`User`, `LLMConfig`, and the `TimestampedModel` /
  `SoftDeleteModel` mixins + `utc_now`); never import from `sparkth.core.models.*` directly.
  Implementation lives in `sparkth/core/models/`.
- [`sparkth/lib/rag.py`](sparkth/lib/rag.py) — RAG public API. Import RAG functionality
  from here (`ingest_document`, `agentic_retrieve_context`, `RetrievedChunk`,
  `IngestionResult`, `RagStatus`, RAG exceptions); never import from `sparkth.rag.*`
  directly. Implementation lives in `sparkth/rag/` (see issue #398).
- [`sparkth/lib/llm.py`](sparkth/lib/llm.py) — LLM public API. Import LLM functionality
  from here (`BaseChatProvider`, `get_provider`, `LLMConfigService`,
  `get_llm_service`, `LLMConfigAdapter`, and the `LLMConfig*` exceptions); never
  import from `sparkth.llm.*` directly. Implementation lives in `sparkth/llm/` (see
  issue #379).
- [`sparkth/lib/plugins.py`](sparkth/lib/plugins.py) — plugin framework public API.
  Plugins import their authoring surface from here (`get_plugin_loader`, `SparkthPlugin`,
  `PluginConfig`, `PluginAccessMiddleware`) as well as `PluginService` / `get_plugin_service`
  and the plugin-service exceptions (`ConfigValidationError`, `InternalServerError`,
  `PluginDisabledError`, `UserPluginResponse`); never import from `sparkth.core.plugins`,
  `sparkth.core.plugins.base`, `sparkth.core.plugins.config_base`,
  `sparkth.core.plugins.middleware` or `sparkth.core.plugins.service` directly.
  Implementation lives in `sparkth/core/plugins/`.
- [`sparkth/lib/permissions/`](sparkth/lib/permissions/__init__.py) — permissions public API
  (scoped RBAC). Import the permission surface from here (`can`, `has_role`,
  `assign_role`, `revoke_role`, `get_permission`,
  `get_permission_scope`, `Permission`); the
  `PERMISSIONS` / `PERMISSION_SCOPES` hooks are imported from the
  `sparkth.lib.permissions.hooks` submodule, the `PermissionScope` class and the
  `GLOBAL` scope from the `sparkth.lib.permissions.scopes` submodule, and the permission
  exception classes (`RoleNotFound`, `PermissionNotFound`, `PermissionScopeNotFound`)
  from the `sparkth.lib.permissions.exceptions` submodule. Plugins declare their own via
  `Permission.create()` / `PermissionScope.create()`. Never import
  from `sparkth.core.permissions.*` directly. Implementation lives in `sparkth/core/permissions/`.
- [`sparkth/lib/analytics/`](sparkth/lib/analytics/__init__.py) — analytics gateway public API.
  Import analytics functionality from here (`ingest_event`, `AnalyticsEventSchema`,
  `ANALYTICS_SCHEMAS`, `initialize_event_registry`, `EventRegistry`,
  `UnknownEventTypeError`, `DuplicateEventTypeError`, `EventNamespaceError`);
  never import from `sparkth.core.analytics.*`
  directly. Plugins subclass `AnalyticsEventSchema` (declaring `event_type` — namespaced under
  the plugin name, e.g. `"slack.message_received"` — and `version`; events are server-only by
  default, set `server_only = False` to allow client emission), register it from their
  `__init__` via `ANALYTICS_SCHEMAS.add_item(self, MyEvent)`, and emit it through `ingest_event`.
  Implementation lives in `sparkth/core/analytics/`.
- [`sparkth/lib/audit/`](sparkth/lib/audit/__init__.py) — audit trail public API. Import the write path
  (`record_event`, `record_event_now`) from here; the self-describing event classes (`BaseAuditEvent`
  and its category tiers `MutationAuditEvent` / `AIActionAuditEvent`, plus `LoginAuditEvent`), their
  value objects (`AuditTarget`, `AuditChange`, `AuditToolCall`,
  `AuditModelInfo`), and `AuditOutcome` from the `sparkth.lib.audit.events` submodule; the actor classes
  (`UserActor` / `SystemActor` / `AnonymousActor`, union alias `AuditActor`), the context classes
  (`AuditRequestContext` / `AuditSystemContext`, union alias `AuditContext`), `AuditActorType`,
  `AuditSource`, and the context helpers from `sparkth.lib.audit.context`; the `AUDIT_EVENTS` hook from
  `sparkth.lib.audit.hooks`; and the audit exceptions from `sparkth.lib.audit.exceptions`. Never
  import from `sparkth.core.audit.*` directly. Implementation lives in `sparkth/core/audit/`. Unlike analytics
  (best-effort), audit writes are fail-closed: mutating and AI actions must not proceed if their audit
  record cannot be written.

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
make services.logs      # Tail logs for the service containers (make services.logs [service])
make db-shell           # PostgreSQL shell
make db-shell-analytics  # PostgreSQL shell on the analytics database
make create-user        # Create user (pass args after --)
```

## Environment Setup

`.env` is committed with working dev defaults (localhost-first: it points at the backing services published by `docker-compose.yml`). For sensitive credentials (Google OAuth, Slack) and local overrides, create a `.env.local` file (git-ignored) — it takes precedence over `.env` and is read by both the native backend and `docker compose`. See the production checklist at the top of `.env` for values that must change before deploying.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `ANALYTICS_DATABASE_URL` | PostgreSQL connection for the separate analytics database (TimescaleDB). Same instance as `DATABASE_URL` by default (Option B); point at another host to isolate it. |
| `SECRET_KEY` | JWT signing key |
| `LLM_ENCRYPTION_KEY` | Fernet key for encrypting stored LLM API keys |
| `REDIS_URL` | Redis for chat session caching and the email-verification resend rate-limit bucket |
| `GOOGLE_CLIENT_ID/SECRET` | Google OAuth (add to `.env.local`) |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_USE_TLS` | Outbound SMTP — dev default is Mailpit (bundled); use Amazon SES, Mailgun, etc. in production |
| `SMTP_FROM_EMAIL` / `SMTP_FROM_NAME` | From-header for verification + other transactional emails |
| `EMAIL_VERIFICATION_TOKEN_TTL_HOURS` | Lifetime of an email-verification token (default 24) |
| `EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS` | Per-email cooldown on the resend endpoint (default 60) |
| `FRONTEND_BASE_URL` | Base URL used in verification email links |
| `TRUSTED_PROXY_HOPS` | Reverse-proxy hops to trust when resolving client IPs from `X-Forwarded-For` (default 0: header ignored, socket peer used); the audit trail records this IP as evidence |
| `CHAT_MAX_TOOL_EXECUTIONS` | Max tool-call iterations the LLM may perform per request (default 50) |
| `CHAT_TITLE_MAX_LENGTH` | Max characters for the auto-extracted conversation title (default 60) |
| `CHAT_TITLE_PROMPT_MAX_CHARS` | Max characters from first user message sent to title-generation LLM (default 500) |
| `CHAT_TITLE_LLM_MAX_TOKENS` | Max tokens the title-generation LLM may produce (default 20) |
| `CHAT_TITLE_DB_MAX_LENGTH` | Max characters stored in the conversation title column (default 255) |
| `CHAT_TITLE_LLM_TEMPERATURE` | Temperature for title-generation LLM calls (default 0.3) |

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

**Permission system → README.** Whenever you change the permission system — declare or remove a permission or scope kind (via `Permission.create()` / `PermissionScope.create()`, which feed the `PERMISSIONS` / `PERMISSION_SCOPES` hooks), add or remove a role, or change how scopes, the lookup helpers, or assignments behave — update the "Permission Management System" section of [`README.md`](README.md) in the same PR. The shipped scopes/roles tables and the extension guide must stay accurate so the README grows with the codebase and is reviewed alongside the change.

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
| Plugin development guide | [sparkth/core/plugins/PLUGIN_GUIDE.md](sparkth/core/plugins/PLUGIN_GUIDE.md) |
| Frontend plugin development | [frontend/README.md](frontend/README.md) |
| GitHub project management (issues, PRs, LLM notices) | [.claude/skills/sparkth-project-management/SKILL.md](.claude/skills/sparkth-project-management/SKILL.md) |

## GitHub Project Management

When creating or editing GitHub issues, posting proposed solutions, opening pull requests, or committing LLM-generated code, follow the conventions in the [`sparkth-project-management`](.claude/skills/sparkth-project-management/SKILL.md) skill.
