#!/usr/bin/env bash
# Ephemeral SQLite backend for the local Playwright E2E suite.
#
# Deletes any previous e2e.db so every run starts from a clean database, builds
# the schema, seeds the superuser plus the @example.com whitelist, then serves
# the API on :7727. DATABASE_URL (sqlite:///./e2e.db) and REDIS_URL are injected
# by Playwright's webServer.env (see frontend/playwright.config.ts).
#
# Runs from the repo root (Playwright sets cwd to the repo root).
set -euo pipefail

rm -f e2e.db e2e.db-*

uv run python scripts/e2e_init_db.py
uv run python scripts/e2e_seed.py

exec uv run uvicorn app.main:app --host 0.0.0.0 --port 7727
