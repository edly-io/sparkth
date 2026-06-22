#!/bin/bash
# Runs once on first cluster init (empty data volume). Creates the separate
# analytics logical database on the same instance (proposal Option B). The
# TimescaleDB extension itself is enabled by the analytics Alembic migration,
# not here, so managed/prod instances (which don't run init scripts) get it too.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE sparkth_analytics'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sparkth_analytics')\gexec
EOSQL
