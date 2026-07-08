# Configuration

Sparkth is configured through environment variables. This guide covers how to set and
update them; for the variables themselves, see the
[configuration reference](../reference/configuration.md).

## Where values live

- **`.env`** is committed with working dev defaults (localhost-first: it points at the
  backing services published by `docker-compose.yml`). It works out of the box for local
  development.
- **`.env.local`** (git-ignored) holds sensitive credentials (Google OAuth, Slack) and local
  overrides. It takes precedence over `.env` and is read by both the native backend and
  `docker compose`.

In production, override values in `.env.local` — see the production checklist at the top of
`.env` for the values that must change before deploying.

## Updating values

Edit `.env.local` (or `.env` for a non-sensitive dev default), then restart the backend to
apply the change:

```bash
make backend.up.dev
```
