from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.analytics.models import analytics_metadata
from app.core.config import get_settings

settings = get_settings()

config = context.config
db_url = settings.ANALYTICS_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://").replace(
    "sqlite+aiosqlite://", "sqlite://"
)
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Analytics schema lives on its own metadata, never SQLModel.metadata.
target_metadata = analytics_metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a live connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
