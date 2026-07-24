# Configuration reference

Sparkth reads its configuration from environment variables. For how to set and update them
(`.env` vs `.env.local`, precedence, applying changes), see the
[configuration guide](../guides/configuration.md).

## The `.env` file is the source of truth

[`.env`](https://github.com/edly-io/sparkth/blob/main/.env) is committed and carries a
comment on **every** variable the application reads, together with its dev default. It is the
authoritative, always-current list — consult it for the complete set of variables (database
and Redis URLs, secret keys, SMTP settings, Google OAuth, chat tuning, and more). This page
documents only the variables that need narrative beyond that inline comment.

## Feature flags

### `REGISTRATION_ENABLED`

- Type: `boolean (true / false)`
- Default: `false`

Controls whether new user registration is enabled on the frontend.

- If `REGISTRATION_ENABLED=true`, users can sign up via the frontend.
- If `REGISTRATION_ENABLED=false`, the registration form is disabled, preventing new user
  creation. Accounts are then created out-of-band — see the
  [user management guide](../guides/user-management.md).

Changing this flag does not affect existing users.

### `SERVE_FRONTEND`

- Type: `boolean (true / false)`
- Default: `false`

Controls whether the backend serves the static frontend export (`FRONTEND_DIR`,
default `frontend/out`) at `/`.

- If `SERVE_FRONTEND=true`, the backend serves the frontend on its own port — the
  single-container production setup. The production image sets this via `ENV` in the
  `Dockerfile`. Startup fails if the export directory is missing: build it first with
  `make frontend.build`.
- If `SERVE_FRONTEND=false`, the backend serves only the API and MCP endpoints. This is
  the dev default: use the Next.js dev server on `:3000`, which proxies `/api` to the
  backend. It also prevents a leftover local `frontend/out` build from being served
  stale.
