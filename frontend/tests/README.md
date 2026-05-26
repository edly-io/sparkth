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

2. **Bring up the stack**:

   ```bash
   make up                                  # postgres, redis, mailpit, api, frontend
   make create-user -- --username admin \
       --email admin@sparkth.local \
       --password 'Sparkth-admin-1!' \
       --superuser --email-verified
   ```

3. **Run the suite**:

   ```bash
   make test.e2e                            # headless
   make test.e2e.ui                         # interactive UI mode
   make test.e2e tests/login.spec.ts        # single file
   ```

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
via the CLI, then runs the suite. Blob reports are uploaded as artifacts and
server logs are attached on failure.
