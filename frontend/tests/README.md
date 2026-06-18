# Playwright E2E Tests

End-to-end tests for the Sparkth frontend, exercising the live FastAPI backend.

## Layout

```
tests/
  auth.setup.ts        # one-time login; persists storage state for chromium project
  config.ts            # shared env-driven config (FIRST_SUPERUSER, MAILPIT_URL, …)
  dashboard.spec.ts    # authenticated dashboard navigation
  login.spec.ts        # /login form: success, bad creds, unverified email
  sign-up.spec.ts      # /register form + email verification round-trip
  utils/
    user.ts            # random user factory + UI/API login helpers
    mailpit.ts         # Mailpit JSON API client (poll for verification emails)
```

`playwright.config.ts` registers a `setup` project (runs `auth.setup.ts`) and a
`chromium` project that depends on it. Tests that need to be logged out (login,
sign-up) override `storageState` to start with a fresh context.

## Running locally

1. **Install browsers** (one-time):

   ```bash
   make test.e2e.install
   ```

2. **Start the backing services** (Mailpit + Redis; the suite needs Mailpit for
   the sign-up email round-trip and Redis for resend rate-limiting). Postgres is
   started too but goes unused, because E2E runs against its own SQLite database:

   ```bash
   make services.up
   ```

   Stop `make backend.up.dev` if it is running: the E2E run owns `:7727` and
   fails loudly if the port is taken.

3. **Run the suite**:

   ```bash
   make test.e2e                            # headless
   make test.e2e.ui                         # interactive UI mode
   make test.e2e tests/login.spec.ts        # single file
   ```

   `make test.e2e` spins up an ephemeral SQLite backend on `:7727` (a fresh
   `e2e.db` deleted at the start of every run, with the schema built and the
   superuser and `@example.com` whitelist seeded automatically) and the frontend
   on `:3000`, then tears both down. Nothing is seeded into dev Postgres.

By default the suite hits:

| Service  | URL                     |
| -------- | ----------------------- |
| Frontend | `http://localhost:3000` |
| API      | `http://localhost:7727` |
| Mailpit  | `http://localhost:8025` |

Override via env vars (also read from `frontend/.env`): `PLAYWRIGHT_BASE_URL`,
`PLAYWRIGHT_API_URL`, `MAILPIT_URL`, `FIRST_SUPERUSER`, `FIRST_SUPERUSER_PASSWORD`.

## CI

`.github/workflows/playwright.yml` brings up Postgres, Redis, and Mailpit as
service containers, builds the frontend statically and serves it through the
API on `:7727` (matching the production deployment model), seeds the superuser
and whitelist via `scripts/seed_e2e.py`, then runs the suite. Blob reports are uploaded as artifacts and
server logs are attached on failure.

### Local vs CI topology

Local runs hit `next dev` on `:3000` (HMR, dev router) while the API runs on
`:7727`. CI builds the frontend statically and serves it through the API on
`:7727`: a single origin, no CORS.

Most bugs manifest in both modes, but a few classes only appear in one:
CORS/cookie-scope issues only fire locally; static-export routing quirks
(e.g. `trailingSlash`) and prod env-var inlining only fire in CI. When a CI
failure won't reproduce locally -- or vice versa -- that divergence is usually
the first thing to check.

Local E2E now runs against an ephemeral SQLite database (built with
`create_all`, no migrations), while CI runs against Postgres with real
migrations. SQLite has no pgvector table, so RAG-ingestion flows cannot be
exercised locally; the current specs do not need it.
