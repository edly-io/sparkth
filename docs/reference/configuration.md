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

## Language

### `DEFAULT_LANGUAGE`

The platform-wide default interface language: the fallback value for users who have not
chosen one in their profile and whose browser offers no supported language. A [BCP 47](https://datatracker.ietf.org/doc/html/rfc5646)
tag, and it must be one of the supported languages — `en`, `es` or `fr`. Anything
else fails validation at startup rather than being silently accepted.

Defaults to `en`. The interface locale follows a precedence chain: a signed-in user's
stored `language` preference, when set and still one of the supported languages, is bound
by the authentication dependency once the user is resolved, and wins over everything else;
otherwise the locale middleware's negotiation of the `Accept-Language` header applies;
`DEFAULT_LANGUAGE` is the last resort, used when neither offers a supported tag and outside
any request (background tasks, CLI). See the [translations guide](../guides/translations.md).

This governs interface text only. The language of AI-generated replies and course content
is inferred from the conversation and is not constrained by this setting or by the
supported-languages list.
