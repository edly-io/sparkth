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

## Additional Documentation

| Topic | File |
|---|---|
| Architectural patterns & design decisions | [.claude/docs/architectural_patterns.md](.claude/docs/architectural_patterns.md) |
| Plugin development guide | [app/plugins/PLUGIN_GUIDE.md](app/plugins/PLUGIN_GUIDE.md) |
| Frontend plugin development | [frontend/README.md](frontend/README.md) |
