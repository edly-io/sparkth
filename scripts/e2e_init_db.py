"""Build the full application schema on the configured database.

The local Playwright E2E suite runs against an ephemeral SQLite database that
cannot be migrated (the RAG migration needs pgvector, and others need Postgres
enum types), so the schema is created with SQLModel.metadata.create_all, the
same way the unit-test suite builds its schema.

Metadata is populated exactly as app/migrations/env.py does it: `from app.models
import *` registers the core tables and get_plugin_loader() registers the plugin
tables, so SQLModel.metadata is complete before create_all runs.
"""

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import SQLModel

from app.core.db import get_engine
from app.lib.log import get_logger
from app.lib.plugins import get_plugin_loader
from app.models import *  # noqa: F403

logger = get_logger(__name__)


def init_schema(engine: Engine) -> None:
    """Create every application table on `engine`. Idempotent."""
    get_plugin_loader()
    try:
        SQLModel.metadata.create_all(engine)
    except SQLAlchemyError:
        logger.exception("Failed to create the E2E schema")
        raise
    logger.info("E2E schema ready (%d tables)", len(SQLModel.metadata.tables))


def main() -> None:
    init_schema(get_engine())


if __name__ == "__main__":
    main()
