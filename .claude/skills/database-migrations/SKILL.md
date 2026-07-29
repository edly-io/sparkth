---
name: database-migrations
description: Create, apply, and troubleshoot Alembic migrations in Sparkth — the two independent lineages (app and analytics), autogenerate mechanics, the continuous-aggregate backfill step, and resolving split heads. Use whenever adding or altering a database column, table, index, or type, generating a migration, running `make migrations`, or when `alembic heads` reports more than one head.
---

# Database Migrations

**Never edit an existing migration file. No exceptions.** Any schema change — add column, drop
column, rename, alter type, add index — requires a new migration file. Editing one that has already
been applied breaks those environments, causing irreproducible state across dev, staging, and
production.

## Creating a migration

```bash
alembic revision --autogenerate -m "describe your change"
```

**Never hand-craft migration filenames or revision IDs.** Always use
`alembic revision --autogenerate` — it generates a valid random hex revision ID. Hand-crafted IDs
risk tooling confusion and non-hex characters that break Alembic expectations.

## Applying migrations

```bash
make migrations
```

## Two independent lineages

The project has two Alembic lineages:

| Lineage | Config | Migrations directory | Metadata |
|---|---|---|---|
| Application database | `alembic.ini` | `sparkth/migrations/app/` | `SQLModel.metadata` |
| Analytics database | `alembic_analytics.ini` | `sparkth/migrations/analytics/` | `sparkth.core.analytics.models.analytics_metadata` |

`make migrations` applies both. Generate an analytics migration with:

```bash
alembic -c alembic_analytics.ini revision --autogenerate -m "..."
```

The two databases never share metadata.

## Continuous aggregates need a one-off backfill after migrating

A TimescaleDB continuous aggregate is created `WITH NO DATA` — creating it with data would backfill
inside Alembic's transaction. Its refresh policy only covers a trailing window, so once the first
policy run advances the materialization watermark, buckets older than that window vanish from the
view and pre-migration history is lost.

After applying an analytics migration that adds a continuous aggregate, run this once on
PostgreSQL to full-refresh it (`refresh_continuous_aggregate` over the whole range):

```bash
make analytics-backfill
```

It is idempotent and a no-op on SQLite.

## Preventing split heads

Multiple Alembic heads occur when two branches each generate a migration from the same parent
revision and merge independently. Before creating a new migration, always check for existing heads:

```bash
alembic heads
```

If there are already multiple heads, merge them first:

```bash
alembic merge heads -m "merge migration heads"
```

After merging a PR that adds a migration, any other in-flight branch that also adds a migration
must rebase so its `down_revision` points to the new tip — otherwise merging it will create another
split head.
